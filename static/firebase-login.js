"use strict"

// import firebase
import { initializeApp } from "https://www.gstatic.com/firebasejs/12.9.0/firebase-app.js"
import { getAuth, createUserWithEmailAndPassword, signInWithEmailAndPassword, signOut }
    from "https://www.gstatic.com/firebasejs/12.9.0/firebase-auth.js"

// your web app's firebase configuration
const firebaseConfig = {
    apiKey: "AIzaSyBthp4pBW8fRkhJ6Ee7qiOYDiF-C7_Ls90",
    authDomain: "cloudfirebase-d816e.firebaseapp.com",
    projectId: "cloudfirebase-d816e",
    storageBucket: "cloudfirebase-d816e.firebasestorage.app",
    messagingSenderId: "987433699281",
    appId: "1:987433699281:web:39db7a51f4b88f5efd02f0"
}

window.addEventListener("load", function() {

    const app = initializeApp(firebaseConfig)
    const auth = getAuth()
    updateUI(document.cookie)

    console.log("hello world load")

    // signup of a new user to firebase
    document.getElementById("sign-up").addEventListener('click', function() {
        const email = document.getElementById("email").value
        const password = document.getElementById("password").value

        createUserWithEmailAndPassword(auth, email, password)
            .then((userCredential) => {

                // we have created a user
                const user = userCredential.user

                // get the id token for the user who just logged in and force a redirect to /
                user.getIdToken().then((token) => {
                    document.cookie = "token=" + token + "; path=/; SameSite=Strict";
                    window.location = "/";
                })

            })
            .catch((error) => {
                // issue for signup that we will drop to console
                console.log(error.code + error.message);
            })
    })

    // login of an existing user
    document.getElementById("login").addEventListener('click', function() {
        const email = document.getElementById("email").value
        const password = document.getElementById("password").value

        signInWithEmailAndPassword(auth, email, password)
            .then((userCredential) => {

                const user = userCredential.user

                user.getIdToken().then((token) => {
                    document.cookie = "token=" + token + "; path=/; SameSite=Strict";
                    window.location = "/";
                })

            })
            .catch((error) => {
                console.log(error.code + error.message)
            })
    })

    // sign out of firebase
    document.getElementById("sign-out").addEventListener('click', function() {

        signOut(auth).then(() => {
            // delete the cookie by setting expiry to epoch
            document.cookie = "token=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
            window.location = "/";
        })
        .catch((error) => {
            console.log(error.code + error.message)
        })

    })

})

// update UI based on cookie
function updateUI(cookie) {

    const loginBox = document.getElementById("login-box")
    const signOutButton = document.getElementById("sign-out")

    if (cookie.includes("token=")) {
        loginBox.hidden = true
        signOutButton.hidden = false
    } else {
        loginBox.hidden = false
        signOutButton.hidden = true
    }
}
// function that will take the cookie and will return the value associated with it to the caller
function parseCookieToken(cookie) {
    // split the cookie out on the basis of the semi-colon
    var strings = cookie.split(';');

    // go through each of the strings
    for (let i = 0; i < strings.length; i++) {
        // split the string based on the = sign. if the LHS is token then return the RHS immediately
        var temp = strings[i].split('=');
        if (temp[0] == "token") {
            return temp[1];
        }
    }

    // if we get to this point then the token wasn't in the cookie so return the empty string
    return "";
}