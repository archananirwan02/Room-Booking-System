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
async def view_room(room_id: str, request: Request):

    room = rooms_doc.find_one({"_id": ObjectId(room_id)})
    day_list = list(days_doc.find({"room_id": ObjectId(room_id)}))

    return templates.TemplateResponse(
        "rooms.html",
        {
            "request": request,
            "room": room,
            "days": day_list
        }
    )

# Add Room
@app.post("/add-room")
async def add_room(request: Request):
    form = await request.form()
    room_no = form.get("room_no")
    floor_no = form.get("floor_no")

    room_exists = rooms_doc.find_one({"room_no": room_no})
    
    if room_exists:
        # Optionally, you can redirect or show a message
        print(f"Room '{room_no}' already exists.")
        return RedirectResponse("/?error=room_exists", status_code=303)
    
    # Insert only if not found
    rooms_doc.insert_one({
        "room_no": room_no,
        "floor_no": floor_no,
        "days": []
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
