importScripts(
    "https://www.gstatic.com/firebasejs/12.17.1/firebase-app-compat.js"
);

importScripts(
    "https://www.gstatic.com/firebasejs/12.17.1/firebase-messaging-compat.js"
);

firebase.initializeApp({
    apiKey: "AIzaSyCMJifhJvj5vVU8j6sHfrObzssCR_dwDMA",
    authDomain: "novagaming-ce687.firebaseapp.com",
    projectId: "novagaming-ce687",
    storageBucket: "novagaming-ce687.firebasestorage.app",
    messagingSenderId: "526729640693",
    appId: "1:526729640693:web:43edf8678e49d2f2ca23bc"
});

const messaging = firebase.messaging();

messaging.onBackgroundMessage(
    function(payload) {

        console.log(
            "Notification reçue en arrière-plan :",
            payload
        );

        const notificationTitle =
            payload.notification?.title ||
            "NovaGaming";

        const notificationOptions = {

            body:
                payload.notification?.body ||
                "Nouvelle notification",

            icon: "/static/favicon.ico"
        };

        self.registration.showNotification(
            notificationTitle,
            notificationOptions
        );
    }
);
