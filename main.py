from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import google.oauth2.id_token
from google.auth.transport import requests
import starlette.status as status
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from urllib.parse import quote_plus
from bson import ObjectId
from fastapi import Form
from datetime import datetime, timedelta



username = quote_plus("archana")
password = quote_plus("Manish@123")

# connection string to our MongoDB NoSQL database
uri = f"mongodb+srv://{username}:{password}@cluster0.z9iumxa.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

# Create a new client and connect to the server
client = MongoClient(uri, server_api=ServerApi('1'))

# Send a ping to confirm a successful connection to the database
try:
    client.admin.command('ping')
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    print(e)

# define the app that will contain all of our routing for FastAPI
app = FastAPI()

# open up a database in MongoDB and open the collections we will need
db = client['A1-3199429']
rooms_doc = db["rooms"]
days_doc = db["days"]
bookings_doc = db["bookings"]


# we need a request object to be able to talk to firebase for verifying user logins
firebase_request_adapter = requests.Request()

# define the static and templates directories
app.mount('/static', StaticFiles(directory='static'), name='static')
templates = Jinja2Templates(directory='templates')


# function that we will use to validate an id_token
def validateFirebaseToken(id_token):
    if not id_token:
        return None

    user_token = None
    try:
        user_token = google.oauth2.id_token.verify_firebase_token(
            id_token, firebase_request_adapter)
    except ValueError as err:
        print(str(err))

    return user_token


# root route
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    id_token = request.cookies.get('token')
    error_message = None
    invalid_time_message = None
    user_token = None
    success_message = None

    user_token = validateFirebaseToken(id_token)
    if not user_token:
        return templates.TemplateResponse(
            'main.html',
            {
                'request': request,
                'user_token': None,
                'error_message': None
            }
        )

    error_flag = request.query_params.get("error")
    if error_flag == "room_exists":
        error_message = "Room already exists."
    elif error_flag == "invalid_time":
        invalid_time_message = "End time must be later than start time."

    success_flag = request.query_params.get("success")
    if success_flag == "booking_created":
        success_message = "Room booked successfully!"


    room_list = list(rooms_doc.find())
    return templates.TemplateResponse(
        'main.html',
        {
            'request': request,
            'user_token': user_token,
            'error_message': error_message,
            'invalid_time_message': invalid_time_message,
            'room_list': room_list,
            'success_message': success_message
        }
    )

# Get Room Details
@app.get("/rooms/{room_id}", response_class=HTMLResponse)
async def view_room(room_id: str, req: Request):

    room = rooms_doc.find_one({"_id": ObjectId(room_id)})
    if not room:
        return RedirectResponse("/", status_code=303)


    # Find all days for this room
    day_list = list(days_doc.find({"room_id": ObjectId(room_id)}))
    day_ids = [d["_id"] for d in day_list]

    # Find all bookings for this room
    bookings = list(bookings_doc.find({"day_id": {"$in": day_ids}}))

    # Attach readable info
    for b in bookings:
        day = next(d for d in day_list if d["_id"] == b["day_id"])
        b["date"] = day["date"]

    # ---- TASK 15: Occupancy for next 5 days ----
    occupancy_list = []
    today = datetime.today()

    calendar = []
    earliest_free = None

    WORK_START = 9 * 60   # 09:00
    WORK_END = 18 * 60    # 18:00
    WORK_TOTAL = WORK_END - WORK_START  # 540


    for i in range(5):
        day_date = (today + timedelta(days=i)).strftime("%Y-%m-%d")

        # Find day document for this date
        day = days_doc.find_one({"room_id": ObjectId(room_id), "date": day_date})

        if not day:
            occupancy_list.append({"date": day_date, "percent": 0})
            calendar.append({"date": day_date, "bookings": []})
            
            if earliest_free is None:
                earliest_free = {"date": day_date, "time": "09:00"}
            continue

        # Get bookings for this day
        day_bookings = list(bookings_doc.find({"day_id": day["_id"]}))

        # calendar structure (Task 17)
        calendar_day = []
        for b in day_bookings:
            calendar_day.append({
                "start_time": b["start_time"],
                "end_time": b["end_time"],
                "user_email": b["user_email"]
            })
        calendar.append({"date": day_date, "bookings": calendar_day})

        # occupancy (Task 15)
        total_minutes = 0
        intervals = []
        for b in day_bookings:
            start = max(time_to_min(b["start_time"]), WORK_START)
            end = min(time_to_min(b["end_time"]), WORK_END)
            if end > start:
                total_minutes += (end - start)
                intervals.append((start, end))

        percent = round((total_minutes / WORK_TOTAL) * 100, 2)
        occupancy_list.append({"date": day_date, "percent": percent})

        # earliest free time (Task 16)
        if earliest_free is None:
            if not intervals:
                earliest_free = {"date": day_date, "time": "09:00"}
            else:
                intervals.sort()
                current = WORK_START
                for s, e in intervals:
                    if s > current:
                        earliest_free = {
                            "date": day_date,
                            "time": minutes_to_time(current)
                        }
                        break
                    current = max(current, e)
                if earliest_free is None and current < WORK_END:
                    earliest_free = {
                        "date": day_date,
                        "time": minutes_to_time(current)
                    }


    return templates.TemplateResponse(
        "rooms.html",
        {
            "request": req,
            "room": room,
            "bookings": bookings,
            "occupancy": occupancy_list,
            "earliest_free": earliest_free,
            "calendar": calendar
        }
    )

# Add Room
@app.post("/add-room")
async def add_room(request: Request):
    form = await request.form()
    room_no = form.get("room_no")
    floor_no = form.get("floor_no")

    id_token = request.cookies.get("token")
    user_token = validateFirebaseToken(id_token)
    if not user_token:
        return RedirectResponse("/?error=not_logged_in", status_code=303)

    room_exists = rooms_doc.find_one({"room_no": room_no})
    
    if room_exists:
        # Optionally, you can redirect or show a message
        print(f"Room '{room_no}' already exists.")
        return RedirectResponse("/?error=room_exists", status_code=303)
    
    # Insert only if not found
    rooms_doc.insert_one({
        "room_no": room_no,
        "floor_no": floor_no,
        "days": [],
        "created_by": user_token["email"]
    })
    return RedirectResponse("/", status_code=303)


# Book a room route
@app.post("/book-room")
async def book_room(req: Request):
    form = await req.form()
    user_token = None

    room_id = form.get("room_no")
    date = form.get("date")
    start_time = form.get("start_time")
    end_time = form.get("end_time")

    # Get logged-in user
    id_token = req.cookies.get("token")
    user_token = validateFirebaseToken(id_token)

    if not user_token:
        return RedirectResponse("/?error=not_logged_in", status_code=303)
    
    if end_time <= start_time:
        return RedirectResponse("/?error=invalid_time", status_code=303)

    # 1. Find or create the Day document
    day = days_doc.find_one({"room_id": ObjectId(room_id), "date": date})

    if not day:
        day_id = days_doc.insert_one({
            "room_id": ObjectId(room_id),
            "date": date
        }).inserted_id
    else:
        day_id = day["_id"]

    # 2. Insert booking
    bookings_doc.insert_one({
        "day_id": day_id,
        "start_time": start_time,
        "end_time": end_time,
        "user_email": user_token["email"]
    })

    return RedirectResponse("/?success=booking_created", status_code=303)


# Route for All my bookings
@app.get("/my-bookings", response_class=HTMLResponse)
async def my_bookings(req: Request):

    success_message = None

    # Get logged-in user
    id_token = req.cookies.get("token")
    user_token = validateFirebaseToken(id_token)

    if not user_token:
        return RedirectResponse("/?error=not_logged_in", status_code=303)

    user_email = user_token["email"]

    success_flag = req.query_params.get("success")

    if success_flag == "booking_deleted":
        success_message = "Booking deleted successfully!"


    # Fetch all bookings for this user
    user_bookings = list(bookings_doc.find({"user_email": user_email}))

    # Attach room + date info
    for b in user_bookings:
        day = days_doc.find_one({"_id": ObjectId(b["day_id"])})
        if not day:
            continue  # skip corrupted booking
        room = rooms_doc.find_one({"_id": ObjectId(day["room_id"])})
        b["date"] = day["date"]
        b["room_no"] = room["room_no"]

    return templates.TemplateResponse(
        "bookings.html",
        {"request": req, 
         "bookings": user_bookings,
         "success_message": success_message}
    )


# Show all bookings current user has made on specific room
@app.get("/my-bookings-room", response_class=HTMLResponse)
async def my_bookings_room(req: Request, room_id: str):

    success_message = None

    # Logged-in user
    id_token = req.cookies.get("token")
    user_token = None

    user_token = validateFirebaseToken(id_token)

    if not user_token:
        return RedirectResponse("/?error=not_logged_in", status_code=303)
    
    success_flag = req.query_params.get("success")

    if success_flag == "booking_deleted":
        success_message = "Booking deleted successfully!"

    user_email = user_token["email"]

    # Find all days for this room
    room_days = list(days_doc.find({"room_id": ObjectId(room_id)}))
    day_ids = [d["_id"] for d in room_days]

    # Find bookings for this user on those days
    user_bookings = list(bookings_doc.find({
        "user_email": user_email,
        "day_id": {"$in": day_ids}
    }))

    # Attach readable info
    room = rooms_doc.find_one({"_id": ObjectId(room_id)})

    for b in user_bookings:
        day = days_doc.find_one({"_id": ObjectId(b["day_id"])})
        b["date"] = day["date"]
        b["room_no"] = room["room_no"]

    return templates.TemplateResponse(
        "bookings.html",
        {"request": req, 
         "bookings": user_bookings,
         "success_message": success_message}
    )

# Delete a booking route
@app.post("/delete-room-booking")
async def delete_booking(req: Request):
    form = await req.form()
    booking_id = form.get("booking_id")

    id_token = req.cookies.get("token")
    user_token = None

    user_token = validateFirebaseToken(id_token)

    if not user_token:
        return RedirectResponse("/?error=not_logged_in", status_code=303)
    
    user_email = user_token["email"]

    if not user_email:
        return RedirectResponse("/", status_code=303)

    # Delete the booking
    bookings_doc.delete_one({
        "_id": ObjectId(booking_id),
        "user_email": user_email
    })

    # Redirect back to "My Bookings"
    return RedirectResponse("/my-bookings?success=booking_deleted", status_code=303)

# Edit booking route
@app.get("/edit-booking/{booking_id}", response_class=HTMLResponse)
async def edit_booking(req: Request, booking_id: str):
    id_token = req.cookies.get("token")
    user_token = validateFirebaseToken(id_token)
    if not user_token:
        return RedirectResponse("/?error=not_logged_in", status_code=303)

    user_email = user_token["email"]

    booking = bookings_doc.find_one({
        "_id": ObjectId(booking_id),
        "user_email": user_email
    })
    if not booking:
        return RedirectResponse("/my-bookings?error=booking_not_found", status_code=303)

    day = days_doc.find_one({"_id": ObjectId(booking["day_id"])})
    if not day:
        return RedirectResponse("/my-bookings?error=booking_not_found", status_code=303)

    room = rooms_doc.find_one({"_id": ObjectId(day["room_id"])})

    # attach extra fields for template
    booking["date"] = day["date"]
    booking["room_no"] = room["room_no"]
    booking["room_id"] = str(room["_id"])

    return templates.TemplateResponse(
        "edit_booking.html",
        {
            "request": req,
            "booking": booking
        }
    )


# Edit booking POST route
@app.post("/edit-booking")
async def edit_booking(
    req: Request,
    booking_id: str = Form(...),
    room_id: str = Form(...),
    date: str = Form(...),
    start_time: str = Form(...),
    end_time: str = Form(...),
):
    id_token = req.cookies.get("token")
    user_token = validateFirebaseToken(id_token)
    if not user_token:
        return RedirectResponse("/?error=not_logged_in", status_code=303)

    user_email = user_token["email"]

    # basic time validation like in book-room
    if end_time <= start_time:
        return RedirectResponse("/my-bookings?error=invalid_time", status_code=303)

    booking = bookings_doc.find_one({
        "_id": ObjectId(booking_id),
        "user_email": user_email
    })
    if not booking:
        return RedirectResponse("/my-bookings?error=booking_not_found", status_code=303)

    room_obj_id = ObjectId(room_id)

    # find or create Day for this room + date
    day = days_doc.find_one({"room_id": room_obj_id, "date": date})
    if not day:
        day_id = days_doc.insert_one({
            "room_id": room_obj_id,
            "date": date
        }).inserted_id
    else:
        day_id = day["_id"]

    # update booking
    bookings_doc.update_one(
        {
            "_id": ObjectId(booking_id),
            "user_email": user_email
        },
        {
            "$set": {
                "day_id": day_id,
                "start_time": start_time,
                "end_time": end_time
            }
        }
    )

    return RedirectResponse("/my-bookings?success=booking_updated", status_code=303)


# Delete a room without Booking and same User
@app.post("/delete-room")
async def delete_room(req: Request):
    form = await req.form()
    room_id = form.get("room_id")

    id_token = req.cookies.get("token")
    user_token = validateFirebaseToken(id_token)
    if not user_token:
        return RedirectResponse("/?error=not_logged_in", status_code=303)

    user_email = user_token["email"]
    room_obj_id = ObjectId(room_id)

    #room exists and was created by this user
    room = rooms_doc.find_one({
        "_id": room_obj_id,
        "created_by": user_email
    })
    if not room:
        # either not found or not creator
        return RedirectResponse("/?error=room_delete_forbidden", status_code=303)

    #there are no bookings on this room
    room_days = list(days_doc.find({"room_id": room_obj_id}))
    day_ids = [d["_id"] for d in room_days]

    existing_booking = bookings_doc.find_one({"day_id": {"$in": day_ids}})
    if existing_booking:
        return RedirectResponse("/?error=room_has_bookings", status_code=303)

    #delete room and its days
    rooms_doc.delete_one({"_id": room_obj_id})
    days_doc.delete_many({"room_id": room_obj_id})

    return RedirectResponse("/", status_code=303)


# Filter bookings by Day
@app.get("/filter-bookings-by-day", response_class=HTMLResponse)
async def filter_by_day(req: Request):
    date = req.query_params.get("date")
    id_token = req.cookies.get("token")
    user_token = validateFirebaseToken(id_token)
    if not user_token:
        return RedirectResponse("/?error=not_logged_in", status_code=303)

    if not date:
        return RedirectResponse("/", status_code=303)

    #Find all days matching this date
    matching_days = list(days_doc.find({"date": date}))
    day_ids = [d["_id"] for d in matching_days]

    #Find all bookings on those days
    bookings = list(bookings_doc.find({"day_id": {"$in": day_ids}}))

    # Attach room + time info
    for b in bookings:
        day = next(d for d in matching_days if d["_id"] == b["day_id"])
        room = rooms_doc.find_one({"_id": day["room_id"]})
        b["room_no"] = room["room_no"]
        b["date"] = date

    return templates.TemplateResponse(
        "filter_booking.html",
        {
            "request": req,
            "bookings": bookings,
            "selected_date": date
        }
    )

# Helper function to convert the time into minutes
def time_to_min(t):
    h, m = map(int, t.split(":"))
    return h * 60 + m

def minutes_to_time(m: int) -> str:
    h = m // 60
    mm = m % 60
    return f"{h:02d}:{mm:02d}"