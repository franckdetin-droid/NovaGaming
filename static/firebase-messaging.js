import { initializeApp } from "https://www.gstatic.com/firebasejs/12.17.1/firebase-app.js";
import {
    getMessaging,
    getToken,
    onMessage
} from "https://www.gstatic.com/firebasejs/12.17.1/firebase-messaging.js";

const firebaseConfig = {
    apiKey: "TAIzaSyCMJifhJvj5vVU8j6sHfrObzssCR_dwDMA",
    authDomain: "novagaming-ce687.firebaseapp.com",
    projectId: "novagaming-ce687",
    storageBucket: "novagaming-ce687.firebasestorage.app",
    messagingSenderId: "526729640693",
    appId: "1:526729640693:web:43edf8678e49d2f2ca23bc"
};

const app = initializeApp(firebaseConfig);
const messaging = getMessaging(app);

async function activerNotifications() {

    try {

        const permission =
            await Notification.requestPermission();

        if (permission !== "granted") {
            console.log("Notifications refusées.");
            return;
        }

        const token = await getToken(
            messaging,
            {
                vapidKey: "BOY2CvvWDg9YnB1oZnQWHMT-eQw5cCH-aN2oT5yC8AiMotmqOuUiYsaHp2Ua3YXQcwE-99f4u41DHl-j8C7C3Ic"
            }
        );

        if (!token) {
            console.log("Token FCM introuvable.");
            return;
        }

        await fetch("/api/token-fcm", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                token: token
            })
        });

        console.log(
            "✅ Token FCM enregistré."
        );

    } catch (erreur) {

        console.error(
            "❌ Erreur notifications :",
            erreur
        );
    }
}

onMessage(messaging, (payload) => {

    console.log(
        "Notification reçue :",
        payload
    );

});

window.activerNotifications =
    activerNotifications;
