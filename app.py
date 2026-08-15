# ==========================
# GAME STORE - APP.PY
# PARTIE 1/4
# ==========================

import os

import cloudinary
import cloudinary.uploader

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    abort,
    send_from_directory
)
from datetime import datetime, timezone
from functools import wraps

from supabase import create_client, Client
# ==========================
# FIREBASE CLOUD MESSAGING
# ==========================

import json

import firebase_admin
from firebase_admin import (
    credentials,
    messaging
)


# ==========================
# INITIALISATION FIREBASE
# ==========================

if not firebase_admin._apps:

    firebase_json = os.environ.get(
        "FIREBASE_SERVICE_ACCOUNT"
    )

    if not firebase_json:

        print(
            "⚠️ FIREBASE_SERVICE_ACCOUNT "
            "n'est pas configurée."
        )

    else:

        try:

            service_account = json.loads(
                firebase_json
            )

            cred = credentials.Certificate(
                service_account
            )

            firebase_admin.initialize_app(
                cred
            )

            print(
                "✅ Firebase Cloud Messaging "
                "initialisé."
            )

        except Exception as e:

            print(
                "❌ ERREUR INITIALISATION FIREBASE :",
                str(e)
            )


# ==========================
# ENVOYER UNE NOTIFICATION PUSH
# ==========================

def envoyer_notification_push(
    token,
    titre,
    message,
    image_url=None
):

    if not token:

        return False

    try:

        notification = messaging.Notification(
            title=titre,
            body=message
        )

        # ==========================
        # NOTIFICATION WEB
        # ==========================

        webpush_notification = (
            messaging.WebpushNotification(
                title=titre,
                body=message,
                image=image_url
            )
        )

        webpush = messaging.WebpushConfig(
            notification=webpush_notification
        )

        message_firebase = messaging.Message(
            notification=notification,
            token=token,
            webpush=webpush
        )

        resultat = messaging.send(
            message_firebase
        )

        print(
            "✅ Notification Firebase envoyée :",
            resultat
        )

        return True

    except Exception as e:

        print(
            "❌ ERREUR NOTIFICATION FIREBASE :",
            str(e)
        )

        return False
# ==========================
# CONFIGURATION FLASK
# ==========================

app = Flask(__name__)

app.secret_key = "CHANGE-MOI-PAR-UNE-CLE-SECRETE"


# ==========================
# CODE ADMIN
# ==========================

CODE_ADMIN = "3004"


# ==========================
# SUPABASE
# ==========================

SUPABASE_URL = os.environ.get(
    "SUPABASE_URL"
)

SUPABASE_KEY = os.environ.get(
    "SUPABASE_KEY"
)

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)
# ==========================
# CLOUDINARY
# ========================
cloudinary.config(
    cloud_name="zgp2vxel",
    api_key="357264626165689",
    api_secret="CkGRcrzSyk4gR-PIA3WC5jMItFI"
)


# ==========================
# UPLOAD IMAGE
# ==========================

def enregistrer_image(fichier, nom_base):

    if fichier is None:
        return None

    if not fichier.filename:
        return None

    if not fichier.mimetype:
        return None

    if not fichier.mimetype.startswith("image/"):
        return None

    extensions_autorisees = {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".gif"
    }

    extension = os.path.splitext(
        fichier.filename
    )[1].lower()

    if extension not in extensions_autorisees:
        print(
            "Extension non autorisée :",
            extension
        )
        return None

    try:

        resultat = cloudinary.uploader.upload(
            fichier,
            folder="novagaming/jeux",
            resource_type="image"
        )

        image_url = resultat.get(
            "secure_url"
        )

        if not image_url:

            print(
                "Cloudinary n'a pas retourné d'URL."
            )

            return None

        print(
            "IMAGE CLOUDINARY :",
            image_url
        )

        return image_url

    except Exception as e:

        print(
            "ERREUR UPLOAD CLOUDINARY :",
            str(e)
        )

        return None


# ==========================
# PROTECTION ADMIN
# ==========================

def admin_required(f):

    @wraps(f)
    def wrapper(*args, **kwargs):

        if not session.get("admin"):

            return redirect(
                url_for("login")
            )

        return f(*args, **kwargs)

    return wrapper


# ==========================
# ACCUEIL
# ==========================

@app.route("/")
def accueil():

    try:

        resultat = (
            supabase
            .table("jeux")
            .select("*")
            .order("id", desc=True)
            .execute()
        )

        jeux = resultat.data or []

    except Exception as e:

        print(
            "ERREUR SUPABASE ACCUEIL :",
            str(e)
        )

        jeux = []

    return render_template(
        "index.html",
        jeux=jeux
    )


# ==========================
# RECHERCHE
# ==========================

@app.route("/recherche")
def recherche():

    q = request.args.get(
        "q",
        ""
    ).strip()

    try:

        requete = (
            supabase
            .table("jeux")
            .select("*")
        )

        if q:

            resultat = requete.or_(
                f"nom.ilike.%{q}%,"
                f"console.ilike.%{q}%,"
                f"description.ilike.%{q}%"
            ).order(
                "id",
                desc=True
            ).execute()

        else:

            resultat = requete.order(
                "id",
                desc=True
            ).execute()

        jeux = resultat.data or []

    except Exception as e:

        print(
            "ERREUR SUPABASE RECHERCHE :",
            str(e)
        )

        jeux = []

    return render_template(
        "index.html",
        jeux=jeux,
        recherche=q
    )


# ==========================
# PAGE D'UN JEU
# ==========================

@app.route("/jeu/<int:jeu_id>")
def jeu(jeu_id):

    try:

        resultat_jeu = (
            supabase
            .table("jeux")
            .select("*")
            .eq("id", jeu_id)
            .limit(1)
            .execute()
        )

        jeux = resultat_jeu.data or []

        if not jeux:

            abort(404)

        jeu_data = jeux[0]


        resultat_commentaires = (
            supabase
            .table("commentaires")
            .select("*")
            .eq("jeu_id", jeu_id)
            .order("id", desc=True)
            .execute()
        )

        commentaires = (
            resultat_commentaires.data or []
        )

    except Exception as e:

        print(
            "ERREUR SUPABASE PAGE JEU :",
            str(e)
        )

        abort(500)

    return render_template(
        "jeu.html",
        jeu=jeu_data,
        commentaires=commentaires
    )


# ==========================
# TELECHARGEMENT
# ==========================

@app.route(
    "/telecharger/<int:jeu_id>"
)
def telecharger(jeu_id):

    try:

        resultat = (
            supabase
            .table("jeux")
            .select("*")
            .eq("id", jeu_id)
            .limit(1)
            .execute()
        )

        jeux = resultat.data or []

        if not jeux:

            abort(404)

        jeu_data = jeux[0]

        lien = jeu_data.get("lien")

        if not lien:

            return (
                "Lien de téléchargement indisponible.",
                404
            )

        ancien_compteur = (
            jeu_data.get("telechargements")
            or 0
        )

        supabase.table("jeux").update({
            "telechargements":
                ancien_compteur + 1
        }).eq(
            "id",
            jeu_id
        ).execute()

    except Exception as e:

        print(
            "ERREUR TELECHARGEMENT :",
            str(e)
        )

        return (
            "Une erreur est survenue.",
            500
        )

    return redirect(lien)


# ==========================
# COMMENTAIRES
# ==========================

@app.route(
    "/commentaire/<int:jeu_id>",
    methods=["POST"]
)
def commentaire(jeu_id):

    pseudo = request.form.get(
        "pseudo",
        ""
    ).strip()

    texte = request.form.get(
        "commentaire",
        ""
    ).strip()

    if not texte:

        return redirect(
            url_for(
                "jeu",
                jeu_id=jeu_id
            )
        )

    pseudo = pseudo[:50]

    texte = texte[:1000]

    if not pseudo:

        pseudo = "Anonyme"

    try:

        jeu_existe = (
            supabase
            .table("jeux")
            .select("id")
            .eq("id", jeu_id)
            .limit(1)
            .execute()
        )

        if not jeu_existe.data:

            abort(404)


        supabase.table(
            "commentaires"
        ).insert({

            "jeu_id": jeu_id,

            "pseudo": pseudo,

            "commentaire": texte

        }).execute()


        supabase.table(
            "notifications"
        ).insert({

            "titre":
                "Nouveau commentaire 💬",

            "message":
                f"{pseudo} a commenté un jeu.",

            "lu": 0

        }).execute()

    except Exception as e:

        print(
            "ERREUR COMMENTAIRE :",
            str(e)
        )

    return redirect(
        url_for(
            "jeu",
            jeu_id=jeu_id
        )
    )


# ==========================
# CONNEXION ADMIN
# ==========================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if session.get("admin"):

        return redirect(
            url_for("admin")
        )

    erreur = None

    if request.method == "POST":

        code = request.form.get(
            "code",
            ""
        ).strip()

        if not code:

            code = request.form.get(
                "password",
                ""
            ).strip()

        if code == CODE_ADMIN:

            session["admin"] = True

            return redirect(
                url_for("admin")
            )

        erreur = (
            "Code administrateur incorrect."
        )

    return render_template(
        "login.html",
        erreur=erreur
    )


# ==========================
# DECONNEXION
# ==========================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("accueil")
            )
    # ==========================
# GAME STORE - APP.PY
# PARTIE 2/4
# ==========================


# ==========================
# ADMINISTRATION
# ==========================

@app.route("/admin")
@admin_required
def admin():

    try:

        # ==========================
        # JEUX
        # ==========================

        resultat_jeux = (
            supabase
            .table("jeux")
            .select("*")
            .order("id", desc=True)
            .execute()
        )

        jeux = resultat_jeux.data or []


        # ==========================
        # TOTAL JEUX
        # ==========================

        resultat_total_jeux = (
            supabase
            .table("jeux")
            .select("id", count="exact")
            .execute()
        )

        total_jeux = (
            resultat_total_jeux.count
            or 0
        )


        # ==========================
        # TOTAL TELECHARGEMENTS
        # ==========================

        resultat_telechargements = (
            supabase
            .table("jeux")
            .select("telechargements")
            .execute()
        )

        total_telechargements = 0

        for jeu_data in (
            resultat_telechargements.data or []
        ):

            total_telechargements += (
                jeu_data.get("telechargements")
                or 0
            )


        # ==========================
        # TOTAL COMMENTAIRES
        # ==========================

        resultat_total_commentaires = (
            supabase
            .table("commentaires")
            .select("id", count="exact")
            .execute()
        )

        total_commentaires = (
            resultat_total_commentaires.count
            or 0
        )


        # ==========================
        # DERNIERS COMMENTAIRES
        # ==========================

        resultat_commentaires = (
            supabase
            .table("commentaires")
            .select("*")
            .order("id", desc=True)
            .limit(30)
            .execute()
        )

        commentaires_admin = (
            resultat_commentaires.data or []
        )


        # ==========================
        # NOTIFICATIONS
        # ==========================

        resultat_notifications = (
            supabase
            .table("notifications")
            .select("*")
            .order("id", desc=True)
            .limit(10)
            .execute()
        )

        notifications_admin = (
            resultat_notifications.data or []
        )


    except Exception as e:

        print(
            "ERREUR ADMIN SUPABASE :",
            str(e)
        )

        jeux = []
        total_jeux = 0
        total_telechargements = 0
        total_commentaires = 0
        commentaires_admin = []
        notifications_admin = []


    return render_template(
        "admin.html",

        jeux=jeux,

        total_jeux=
            total_jeux,

        total_telechargements=
            total_telechargements,

        total_commentaires=
            total_commentaires,

        commentaires_admin=
            commentaires_admin,

        notifications_admin=
            notifications_admin
    )


# ==========================
# AJOUTER UN JEU
# ==========================

@app.route(
    "/admin/ajouter",
    methods=["POST"]
)
@admin_required
def ajouter():

    # ==========================
    # INFORMATIONS
    # ==========================

    nom = request.form.get(
        "nom",
        ""
    ).strip()

    console = request.form.get(
        "console",
        ""
    ).strip()

    description = request.form.get(
        "description",
        ""
    ).strip()

    taille = request.form.get(
        "taille",
        ""
    ).strip()

    version = request.form.get(
        "version",
        ""
    ).strip()

    langue = request.form.get(
        "langue",
        ""
    ).strip()

    couverture = request.form.get(
        "couverture",
        ""
    ).strip()

    lien = request.form.get(
        "lien",
        ""
    ).strip()


    # ==========================
    # VERIFICATIONS
    # ==========================

    if not nom:

        return (
            "Le nom du jeu est obligatoire.",
            400
        )

    if not lien:

        return (
            "Le lien de téléchargement est obligatoire.",
            400
        )


    # ==========================
    # COUVERTURE
    # ==========================

    couverture_file = request.files.get(
        "couverture_file"
    )

    if (
        couverture_file
        and couverture_file.filename
    ):

        image_couverture = (
            enregistrer_image(
                couverture_file,
                "couverture"
            )
        )

        if image_couverture:

            couverture = (
                image_couverture
            )


    # ==========================
    # GALERIE
    # ==========================

    fichiers_images = (
        request.files.getlist("images")
    )

    images = []

    for fichier in fichiers_images[:10]:

        if not fichier:
            continue

        if not fichier.filename:
            continue

        image_url = enregistrer_image(
            fichier,
            "galerie"
        )

        if image_url:

            images.append(
                image_url
            )


    # Compléter jusqu'à 10 images

    while len(images) < 10:

        images.append("")


    image1 = images[0]
    image2 = images[1]
    image3 = images[2]
    image4 = images[3]
    image5 = images[4]
    image6 = images[5]
    image7 = images[6]
    image8 = images[7]
    image9 = images[8]
    image10 = images[9]


    # ==========================
    # INSERTION SUPABASE
    # ==========================

    try:

        resultat = (
            supabase
            .table("jeux")
            .insert({

                "nom":
                    nom,

                "console":
                    console,

                "description":
                    description,

                "taille":
                    taille,

                "version":
                    version,

                "langue":
                    langue,

                "couverture":
                    couverture,

                "image1":
                    image1,

                "image2":
                    image2,

                "image3":
                    image3,

                "image4":
                    image4,

                "image5":
                    image5,

                "image6":
                    image6,

                "image7":
                    image7,

                "image8":
                    image8,

                "image9":
                    image9,

                "image10":
                    image10,

                "lien":
                    lien,

                "telechargements":
                    0

            })
            .execute()
        )

        # ==========================
        # NOTIFICATION
        # ==========================

        supabase.table(
            "notifications"
        ).insert({

            "titre":
                "Nouveau jeu disponible 🎮",

            "message":
                f"{nom} vient d'être ajouté au catalogue.",

            "lu":
                0

        }).execute()


        # ==========================
        # NOTIFICATION PUSH FIREBASE
        # ==========================

        try:

            resultat_tokens = (
                supabase
                .table("tokens_fcm")
                .select("token")
                .execute()
            )

            for element in (
                resultat_tokens.data or []
            ):

                token = element.get("token")

                if token:

                    envoyer_notification_push(
                        token,
                        "Nouveau jeu disponible 🎮",
                        f"{nom} vient d'être ajouté au catalogue.",
                        couverture
                    )

        except Exception as e:

            print(
                "ERREUR PUSH FIREBASE :",
                str(e)
            )


    except Exception as e:

        print(
            "ERREUR AJOUT JEU SUPABASE :",
            str(e)
        )

        return (
            "Erreur lors de l'ajout du jeu.",
            500
        )


    return redirect(
        url_for("admin")
    )

# ==========================
# MODIFIER UN JEU
# ==========================

@app.route(
    "/admin/modifier/<int:jeu_id>",
    methods=["GET", "POST"]
)
@admin_required
def modifier(jeu_id):

    # ==========================
    # RECUPERER LE JEU
    # ==========================

    try:

        resultat = (
            supabase
            .table("jeux")
            .select("*")
            .eq("id", jeu_id)
            .limit(1)
            .execute()
        )

        jeux = resultat.data or []

        if not jeux:

            abort(404)

        jeu_data = jeux[0]


    except Exception as e:

        print(
            "ERREUR RECUPERATION JEU :",
            str(e)
        )

        abort(500)


    # ==========================
    # AFFICHAGE
    # ==========================

    if request.method == "GET":

        return render_template(
            "modifier.html",
            jeu=jeu_data
        )


    # ==========================
    # INFORMATIONS
    # ==========================

    nom = request.form.get(
        "nom",
        ""
    ).strip()

    console = request.form.get(
        "console",
        ""
    ).strip()

    description = request.form.get(
        "description",
        ""
    ).strip()

    taille = request.form.get(
        "taille",
        ""
    ).strip()

    version = request.form.get(
        "version",
        ""
    ).strip()

    langue = request.form.get(
        "langue",
        ""
    ).strip()

    couverture = request.form.get(
        "couverture",
        ""
    ).strip()

    lien = request.form.get(
        "lien",
        ""
    ).strip()


    # ==========================
    # VERIFICATIONS
    # ==========================

    if not nom:

        return (
            "Le nom du jeu est obligatoire.",
            400
        )

    if not lien:

        return (
            "Le lien de téléchargement est obligatoire.",
            400
        )


    # ==========================
    # COUVERTURE
    # ==========================

    couverture_file = request.files.get(
        "couverture_file"
    )

    if (
        couverture_file
        and couverture_file.filename
    ):

        nouvelle_couverture = (
            enregistrer_image(
                couverture_file,
                "couverture"
            )
        )

        if nouvelle_couverture:

            couverture = (
                nouvelle_couverture
            )

    else:

        if not couverture:

            couverture = (
                jeu_data.get("couverture")
                or ""
            )


    # ==========================
    # ANCIENNES IMAGES
    # ==========================

    anciennes_images = [

        jeu_data.get("image1") or "",

        jeu_data.get("image2") or "",

        jeu_data.get("image3") or "",

        jeu_data.get("image4") or "",

        jeu_data.get("image5") or "",

        jeu_data.get("image6") or "",

        jeu_data.get("image7") or "",

        jeu_data.get("image8") or "",

        jeu_data.get("image9") or "",

        jeu_data.get("image10") or ""

    ]


    # ==========================
    # NOUVELLES IMAGES
    # ==========================

    fichiers_images = (
        request.files.getlist("images")
    )

    nouvelles_images = []


    for fichier in fichiers_images[:10]:

        if not fichier:
            continue

        if not fichier.filename:
            continue

        image_url = enregistrer_image(
            fichier,
            "galerie"
        )

        if image_url:

            nouvelles_images.append(
                image_url
            )


    # ==========================
    # CHOIX DES IMAGES
    # ==========================

    if nouvelles_images:

        images = nouvelles_images

        while len(images) < 10:

            images.append("")

    else:

        images = anciennes_images


    # ==========================
    # MISE A JOUR SUPABASE
    # ==========================

    try:

        supabase.table(
            "jeux"
        ).update({

            "nom":
                nom,

            "console":
                console,

            "description":
                description,

            "taille":
                taille,

            "version":
                version,

            "langue":
                langue,

            "couverture":
                couverture,

            "image1":
                images[0],

            "image2":
                images[1],

            "image3":
                images[2],

            "image4":
                images[3],

            "image5":
                images[4],

            "image6":
                images[5],

            "image7":
                images[6],

            "image8":
                images[7],

            "image9":
                images[8],

            "image10":
                images[9],

            "lien":
                lien

        }).eq(
            "id",
            jeu_id
        ).execute()


                # ==========================
        # NOTIFICATION
        # ==========================

        supabase.table(
            "notifications"
        ).insert({

            "titre":
                "Jeu modifié ✏️",

            "message":
                f"{nom} a été modifié.",

            "lu":
                0

        }).execute()


        # ==========================
        # NOTIFICATION PUSH FIREBASE
        # ==========================

        try:

            resultat_tokens = (
                supabase
                .table("tokens_fcm")
                .select("token")
                .execute()
            )

            for element in (
                resultat_tokens.data or []
            ):

                token = element.get("token")

                if token:

                    envoyer_notification_push(
                        token,
                        "Jeu modifié ✏️",
                        f"{nom} a été modifié.",
                        couverture
                    )

        except Exception as e:

            print(
                "ERREUR PUSH MODIFICATION :",
                str(e)
            )


    except Exception as e:

        print(
            "ERREUR MODIFICATION SUPABASE :",
            str(e)
        )

        return (
            "Erreur lors de la modification.",
            500
        )


    return redirect(
        url_for("admin")
    )
    # ==========================
# GAME STORE - APP.PY
# PARTIE 3/4
# ==========================


# ==========================
# SUPPRIMER UN JEU
# ==========================

@app.route(
    "/admin/supprimer/<int:jeu_id>"
)
@admin_required
def supprimer(jeu_id):

    try:

        # ==========================
        # VERIFIER LE JEU
        # ==========================

        resultat = (
            supabase
            .table("jeux")
            .select("*")
            .eq("id", jeu_id)
            .limit(1)
            .execute()
        )

        jeux = resultat.data or []

        if not jeux:

            abort(404)

        jeu_data = jeux[0]


        # ==========================
        # SUPPRIMER COMMENTAIRES
        # ==========================

        supabase.table(
            "commentaires"
        ).delete().eq(
            "jeu_id",
            jeu_id
        ).execute()


        # ==========================
        # SUPPRIMER FAVORIS
        # ==========================

        supabase.table(
            "favoris"
        ).delete().eq(
            "jeu_id",
            jeu_id
        ).execute()


        # ==========================
        # SUPPRIMER VUES
        # ==========================

        supabase.table(
            "vues"
        ).delete().eq(
            "jeu_id",
            jeu_id
        ).execute()


        # ==========================
        # SUPPRIMER LE JEU
        # ==========================

        supabase.table(
            "jeux"
        ).delete().eq(
            "id",
            jeu_id
        ).execute()

        # ==========================
        # NOTIFICATION
        # ==========================

        nom_jeu = jeu_data.get(
            "nom",
            "Le jeu"
        )

        couverture_jeu = jeu_data.get(
            "couverture"
        )

        supabase.table(
            "notifications"
        ).insert({

            "titre":
                "Jeu supprimé 🗑️",

            "message":
                f"{nom_jeu} a été supprimé du catalogue.",

            "lu":
                0

        }).execute()


        # ==========================
        # NOTIFICATION PUSH FIREBASE
        # ==========================

        try:

            resultat_tokens = (
                supabase
                .table("tokens_fcm")
                .select("token")
                .execute()
            )

            for element in (
                resultat_tokens.data or []
            ):

                token = element.get("token")

                if token:

                    envoyer_notification_push(
                        token,
                        "Jeu supprimé 🗑️",
                        f"{nom_jeu} a été supprimé du catalogue.",
                        couverture_jeu
                    )

        except Exception as e:

            print(
                "ERREUR PUSH SUPPRESSION :",
                str(e)
            )


    except Exception as e:

        print(
            "ERREUR SUPPRESSION JEU SUPABASE :",
            str(e)
        )

        return (
            "Erreur lors de la suppression du jeu.",
            500
        )


    return redirect(
        url_for("admin")
            )

# ==========================
# SUPPRIMER UN COMMENTAIRE
# ==========================

@app.route(
    "/admin/commentaire/supprimer/<int:commentaire_id>"
)
@admin_required
def supprimer_commentaire(commentaire_id):

    try:

        supabase.table(
            "commentaires"
        ).delete().eq(
            "id",
            commentaire_id
        ).execute()

    except Exception as e:

        print(
            "ERREUR SUPPRESSION COMMENTAIRE :",
            str(e)
        )

        return (
            "Erreur lors de la suppression.",
            500
        )


    return redirect(
        url_for("admin")
    )


# ==========================
# FAVORIS
# ==========================

@app.route(
    "/favori/<int:jeu_id>"
)
def favori(jeu_id):

    # ==========================
    # IDENTIFICATION
    # ==========================

    ip = request.remote_addr


    try:

        # ==========================
        # VERIFIER LE JEU
        # ==========================

        resultat_jeu = (
            supabase
            .table("jeux")
            .select("id")
            .eq("id", jeu_id)
            .limit(1)
            .execute()
        )

        if not resultat_jeu.data:

            abort(404)


        # ==========================
        # VERIFIER FAVORI
        # ==========================

        resultat_favori = (
            supabase
            .table("favoris")
            .select("id")
            .eq("jeu_id", jeu_id)
            .eq("ip", ip)
            .limit(1)
            .execute()
        )


        # ==========================
        # RETIRER DES FAVORIS
        # ==========================

        if resultat_favori.data:

            supabase.table(
                "favoris"
            ).delete().eq(
                "jeu_id",
                jeu_id
            ).eq(
                "ip",
                ip
            ).execute()


        # ==========================
        # AJOUTER AUX FAVORIS
        # ==========================

        else:

            supabase.table(
                "favoris"
            ).insert({

                "jeu_id":
                    jeu_id,

                "ip":
                    ip

            }).execute()


    except Exception as e:

        print(
            "ERREUR FAVORI SUPABASE :",
            str(e)
        )

        return (
            "Erreur lors de la gestion du favori.",
            500
        )


    return redirect(
        url_for(
            "jeu",
            jeu_id=jeu_id
        )
    )


# ==========================
# NOTIFICATIONS
# ==========================

@app.route(
    "/notifications"
)
def notifications():

    try:

        resultat = (
            supabase
            .table("notifications")
            .select("*")
            .order("id", desc=True)
            .execute()
        )

        liste = resultat.data or []

    except Exception as e:

        print(
            "ERREUR NOTIFICATIONS SUPABASE :",
            str(e)
        )

        liste = []


    return render_template(
        "notifications.html",
        notifications=liste
    )


# ==========================
# MARQUER LES NOTIFICATIONS
# COMME LUES
# ==========================

@app.route(
    "/notifications/lues",
    methods=["POST"]
)
def notifications_lues():

    try:

        supabase.table(
            "notifications"
        ).update({

            "lu":
                1

        }).eq(
            "lu",
            0
        ).execute()

    except Exception as e:

        print(
            "ERREUR NOTIFICATIONS LUES :",
            str(e)
        )

        return (
            "Erreur lors de la mise à jour.",
            500
        )


    return redirect(
        url_for("notifications")
    )


# ==========================
# JEUX POPULAIRES
# ==========================

@app.route(
    "/populaires"
)
def populaires():

    try:

        resultat = (
            supabase
            .table("jeux")
            .select("*")
            .order(
                "telechargements",
                desc=True
            )
            .limit(20)
            .execute()
        )

        jeux = resultat.data or []

    except Exception as e:

        print(
            "ERREUR JEUX POPULAIRES :",
            str(e)
        )

        jeux = []


    return render_template(
        "index.html",
        jeux=jeux,
        titre="🔥 Jeux populaires"
    )


# ==========================
# NOUVEAUTÉS
# ==========================

@app.route(
    "/nouveautes"
)
def nouveautes():

    try:

        resultat = (
            supabase
            .table("jeux")
            .select("*")
            .order(
                "date_ajout",
                desc=True
            )
            .limit(20)
            .execute()
        )

        jeux = resultat.data or []

    except Exception as e:

        print(
            "ERREUR NOUVEAUTES :",
            str(e)
        )

        jeux = []


    return render_template(
        "index.html",
        jeux=jeux,
        titre="🆕 Nouveautés"
    )


# ==========================
# COMPTEUR DE VUES
# ==========================

@app.before_request
def compteur_vues():

    # ==========================
    # UNIQUEMENT PAGE JEU
    # ==========================

    if request.endpoint != "jeu":

        return

    if not request.view_args:

        return

    jeu_id = request.view_args.get(
        "jeu_id"
    )

    if not jeu_id:

        return


    ip = request.remote_addr


    try:

        # ==========================
        # VERIFIER UNE VUE RECENTE
        # ==========================

        resultat = (
            supabase
            .table("vues")
            .select("id,date")
            .eq("jeu_id", jeu_id)
            .eq("ip", ip)
            .order(
                "date",
                desc=True
            )
            .limit(1)
            .execute()
        )


        vues = resultat.data or []


        # ==========================
        # VERIFIER LES 30 MINUTES
        # ==========================

        ajouter_vue = True


        if vues:

            date_vue = vues[0].get(
                "date"
            )

            if date_vue:

                from datetime import datetime, timezone

                try:

                    date_vue = (
                        date_vue
                        .replace(
                            "Z",
                            "+00:00"
                        )
                    )

                    date_vue = (
                        datetime.fromisoformat(
                            date_vue
                        )
                    )

                    maintenant = (
                        datetime.now(
                            timezone.utc
                        )
                    )

                    difference = (
                        maintenant
                        - date_vue
                    ).total_seconds()


                    if difference < 1800:

                        ajouter_vue = False

                except Exception:

                    ajouter_vue = True


        # ==========================
        # AJOUTER LA VUE
        # ==========================

        if ajouter_vue:

            supabase.table(
                "vues"
            ).insert({

                "jeu_id":
                    jeu_id,

                "ip":
                    ip

            }).execute()


    except Exception as e:

        print(
            "ERREUR COMPTEUR VUES :",
            str(e)
        )


# ==========================
# NOMBRE DE FAVORIS
# ==========================

@app.context_processor
def fonctions_globales():

    def nombre_favoris(jeu_id):

        try:

            resultat = (
                supabase
                .table("favoris")
                .select(
                    "id",
                    count="exact"
                )
                .eq(
                    "jeu_id",
                    jeu_id
                )
                .execute()
            )

            return (
                resultat.count
                or 0
            )

        except Exception as e:

            print(
                "ERREUR NOMBRE FAVORIS :",
                str(e)
            )

            return 0


    return {
        "nombre_favoris":
            nombre_favoris
    }


# ==========================
# STATISTIQUES GLOBALES
# ==========================

@app.context_processor
def statistiques_globales():

    try:

        # ==========================
        # COMMENTAIRES
        # ==========================

        resultat_commentaires = (
            supabase
            .table("commentaires")
            .select(
                "id",
                count="exact"
            )
            .execute()
        )

        commentaires = (
            resultat_commentaires.count
            or 0
        )


        # ==========================
        # JEUX
        # ==========================

        resultat_jeux = (
            supabase
            .table("jeux")
            .select(
                "id",
                count="exact"
            )
            .execute()
        )

        jeux = (
            resultat_jeux.count
            or 0
        )


        # ==========================
        # TELECHARGEMENTS
        # ==========================

        resultat_downloads = (
            supabase
            .table("jeux")
            .select("telechargements")
            .execute()
        )

        telechargements = 0

        for jeu_data in (
            resultat_downloads.data or []
        ):

            telechargements += (
                jeu_data.get(
                    "telechargements"
                )
                or 0
            )


        # ==========================
        # NOTIFICATIONS NON LUES
        # ==========================

        resultat_notifications = (
            supabase
            .table("notifications")
            .select(
                "id",
                count="exact"
            )
            .eq(
                "lu",
                0
            )
            .execute()
        )

        notifications_non_lues = (
            resultat_notifications.count
            or 0
        )


    except Exception as e:

        print(
            "ERREUR STATISTIQUES SUPABASE :",
            str(e)
        )

        commentaires = 0
        jeux = 0
        telechargements = 0
        notifications_non_lues = 0


    return {

        "total_commentaires":
            commentaires,

        "total_jeux":
            jeux,

        "total_telechargements":
            telechargements,

        "notifications_non_lues":
            notifications_non_lues

}
    # ==========================
# GAME STORE - APP.PY
# PARTIE 4/4
# ==========================


# ==========================
# PAGE 404
# ==========================

@app.errorhandler(404)
def page_introuvable(error):

    return """
    <!DOCTYPE html>
    <html lang="fr">

    <head>

        <meta charset="UTF-8">

        <meta
            name="viewport"
            content="width=device-width, initial-scale=1.0"
        >

        <title>404 - Page introuvable</title>

        <style>

            body {

                margin: 0;

                min-height: 100vh;

                display: flex;

                align-items: center;

                justify-content: center;

                font-family: Arial, sans-serif;

                background: #0f141c;

                color: white;

                text-align: center;

            }


            .error-box {

                padding: 40px 25px;

                max-width: 500px;

            }


            h1 {

                font-size: 80px;

                margin: 0;

            }


            h2 {

                margin: 10px 0;

            }


            p {

                color: #9aa8ba;

            }


            a {

                display: inline-block;

                margin-top: 20px;

                padding: 12px 20px;

                border-radius: 10px;

                background: #4da3ff;

                color: white;

                text-decoration: none;

                font-weight: bold;

            }

        </style>

    </head>


    <body>

        <div class="error-box">

            <h1>404</h1>

            <h2>Page introuvable</h2>

            <p>
                La page que tu recherches
                n'existe pas.
            </p>

            <a href="/">
                🏠 Retour à l'accueil
            </a>

        </div>

    </body>

    </html>
    """, 404


# ==========================
# ERREUR SERVEUR
# ==========================

@app.errorhandler(500)
def erreur_serveur(error):

    return """
    <!DOCTYPE html>
    <html lang="fr">

    <head>

        <meta charset="UTF-8">

        <meta
            name="viewport"
            content="width=device-width, initial-scale=1.0"
        >

        <title>Erreur serveur</title>

        <style>

            body {

                margin: 0;

                min-height: 100vh;

                display: flex;

                align-items: center;

                justify-content: center;

                font-family: Arial, sans-serif;

                background: #0f141c;

                color: white;

                text-align: center;

            }


            .error-box {

                padding: 40px 25px;

                max-width: 500px;

            }


            h1 {

                font-size: 70px;

                margin: 0;

            }


            p {

                color: #9aa8ba;

            }


            a {

                display: inline-block;

                margin-top: 20px;

                padding: 12px 20px;

                border-radius: 10px;

                background: #4da3ff;

                color: white;

                text-decoration: none;

                font-weight: bold;

            }

        </style>

    </head>


    <body>

        <div class="error-box">

            <h1>500</h1>

            <h2>Erreur serveur</h2>

            <p>
                Une erreur est survenue.
                Réessaie dans quelques instants.
            </p>

            <a href="/">
                🏠 Retour à l'accueil
            </a>

        </div>

    </body>

    </html>
    """, 500


# ==========================
# ROBOTS.TXT
# ==========================

@app.route("/robots.txt")
def robots():

    return send_from_directory(
        ".",
        "robots.txt"
    )


# ==========================
# SITEMAP.XML
# ==========================

@app.route("/sitemap.xml")
def sitemap():

    return send_from_directory(
        ".",
        "sitemap.xml"
    )
   

# ==========================
# TEST SUPABASE
# ==========================

@app.route("/test-supabase")
@admin_required
def test_supabase():

    try:

        resultat = (
            supabase
            .table("jeux")
            .select("id")
            .limit(1)
            .execute()
        )

        return {
            "success": True,
            "message": "Connexion Supabase OK",
            "resultat": resultat.data
        }

    except Exception as e:

        return {
            "success": False,
            "message": "Erreur Supabase",
            "error": str(e)
        }, 500
        # ==========================
# ENREGISTRER UN TOKEN FCM
# ==========================

@app.route(
    "/api/token-fcm",
    methods=["POST"]
)
def enregistrer_token_fcm():

    donnees = request.get_json(
        silent=True
    ) or {}

    token = donnees.get(
        "token",
        ""
    ).strip()

    if not token:

        return {
            "success": False,
            "message": "Token manquant."
        }, 400

    try:

        supabase.table(
            "tokens_fcm"
        ).upsert(
            {
                "token": token
            },
            on_conflict="token"
        ).execute()

        return {
            "success": True
        }

    except Exception as e:

        print(
            "ERREUR TOKEN FCM :",
            str(e)
        )

        return {
            "success": False
        }, 500
        # ==========================
# ANALYTICS / STATISTIQUES
# ==========================

from datetime import datetime, timezone


def enregistrer_statistique(
    type_evenement,
    page=None,
    jeu_id=None
):
    try:

        ip = request.headers.get(
            "X-Forwarded-For",
            request.remote_addr
        )

        if ip and "," in ip:
            ip = ip.split(",")[0].strip()

        user_agent = request.headers.get(
            "User-Agent",
            ""
        )

        supabase.table(
            "analytics"
        ).insert({

            "type_evenement":
                type_evenement,

            "page":
                page,

            "jeu_id":
                jeu_id,

            "ip":
                ip,

            "user_agent":
                user_agent,

            "date":
                datetime.now(
                    timezone.utc
                ).isoformat()

        }).execute()

    except Exception as e:

        print(
            "ERREUR ANALYTICS :",
            str(e)
        )


# ==========================
# ENREGISTRER UNE VISITE
# ==========================

@app.route(
    "/api/analytics/visite",
    methods=["POST"]
)
def analytics_visite():

    donnees = request.get_json(
        silent=True
    ) or {}

    page = donnees.get(
        "page",
        "/"
    )

    enregistrer_statistique(
        type_evenement="visite",
        page=page
    )

    return {
        "success": True
    }


# ==========================
# ENREGISTRER LE TEMPS PASSE
# ==========================

@app.route(
    "/api/analytics/temps",
    methods=["POST"]
)
def analytics_temps():

    donnees = request.get_json(
        silent=True
    ) or {}

    page = donnees.get(
        "page",
        "/"
    )

    secondes = donnees.get(
        "secondes",
        0
    )

    try:
        secondes = int(secondes)
    except:
        secondes = 0

    secondes = max(
        0,
        min(secondes, 86400)
    )

    try:

        enregistrer_statistique(
            type_evenement="temps",
            page=page
        )

        supabase.table(
            "analytics"
        ).update({

            "secondes":
                secondes

        }).eq(
            "id",
            (
                supabase
                .table("analytics")
                .select("id")
                .eq(
                    "type_evenement",
                    "temps"
                )
                .eq(
                    "page",
                    page
                )
                .order(
                    "id",
                    desc=True
                )
                .limit(1)
                .execute()
                .data[0]["id"]
            )
            if (
                supabase
                .table("analytics")
                .select("id")
                .eq(
                    "type_evenement",
                    "temps"
                )
                .eq(
                    "page",
                    page
                )
                .order(
                    "id",
                    desc=True
                )
                .limit(1)
                .execute()
                .data
            )
            else -1
        ).execute()

    except Exception as e:

        print(
            "ERREUR TEMPS ANALYTICS :",
            str(e)
        )

    return {
        "success": True
    }


# ==========================
# API STATISTIQUES ADMIN
# ==========================

@app.route(
    "/api/admin/statistiques"
)
@admin_required
def statistiques_admin():

    try:

        # ==========================
        # TOUTES LES DONNÉES
        # ==========================

        resultat = (
            supabase
            .table("analytics")
            .select("*")
            .execute()
        )

        donnees = (
            resultat.data or []
        )


        # ==========================
        # VISITEURS
        # ==========================

        visites = [
            x for x in donnees
            if x.get(
                "type_evenement"
            ) == "visite"
        ]

        visiteurs_total = len(
            visites
        )


        # ==========================
        # VISITEURS UNIQUES
        # ==========================

        ips = set()

        for visite in visites:

            ip = visite.get("ip")

            if ip:
                ips.add(ip)

        visiteurs_uniques = len(ips)


        # ==========================
        # PAGES VUES
        # ==========================

        pages_vues = {}

        for visite in visites:

            page = (
                visite.get("page")
                or "/"
            )

            pages_vues[page] = (
                pages_vues.get(page, 0)
                + 1
            )


        pages_populaires = sorted(
            pages_vues.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]


        # ==========================
        # TEMPS TOTAL
        # ==========================

        temps_total = 0

        temps = [
            x for x in donnees
            if x.get(
                "type_evenement"
            ) == "temps"
        ]

        for element in temps:

            temps_total += (
                element.get(
                    "secondes"
                )
                or 0
            )


        # ==========================
        # TEMPS MOYEN
        # ==========================

        if temps:

            temps_moyen = (
                temps_total / len(temps)
            )

        else:

            temps_moyen = 0


        # ==========================
        # UTILISATEURS ACTIFS
        # ==========================

        maintenant = datetime.now(
            timezone.utc
        )

        utilisateurs_actifs = set()

        for visite in visites:

            date_visite = visite.get(
                "date"
            )

            if not date_visite:
                continue

            try:

                date_obj = datetime.fromisoformat(
                    date_visite.replace(
                        "Z",
                        "+00:00"
                    )
                )

                difference = (
                    maintenant - date_obj
                ).total_seconds()

                if difference <= 300:

                    ip = visite.get("ip")

                    if ip:
                        utilisateurs_actifs.add(ip)

            except:

                continue


        # ==========================
        # RÉPONSE
        # ==========================

        return {

            "success": True,

            "visiteurs_total":
                visiteurs_total,

            "visiteurs_uniques":
                visiteurs_uniques,

            "pages_vues":
                sum(
                    pages_vues.values()
                ),

            "pages_populaires":
                [
                    {
                        "page": page,
                        "visites": nombre
                    }
                    for page, nombre
                    in pages_populaires
                ],

            "utilisateurs_actifs":
                len(
                    utilisateurs_actifs
                ),

            "temps_total_secondes":
                temps_total,

            "temps_moyen_secondes":
                round(
                    temps_moyen,
                    1
                )

        }

    except Exception as e:

        print(
            "ERREUR STATISTIQUES ADMIN :",
            str(e)
        )

        return {

            "success": False,

            "message":
                str(e)

        }, 500


# ==========================
# STATISTIQUES TÉLÉCHARGEMENTS
# ==========================

@app.route(
    "/api/admin/telechargements"
)
@admin_required
def statistiques_telechargements():

    try:

        resultat = (
            supabase
            .table("jeux")
            .select(
                "id,nom,telechargements"
            )
            .order(
                "telechargements",
                desc=True
            )
            .execute()
        )

        jeux = resultat.data or []

        total = 0

        for jeu_data in jeux:

            total += (
                jeu_data.get(
                    "telechargements"
                )
                or 0
            )

        return {

            "success": True,

            "total":
                total,

            "jeux":
                jeux

        }

    except Exception as e:

        print(
            "ERREUR STATS TELECHARGEMENTS :",
            str(e)
        )

        return {

            "success": False,

            "message":
                str(e)

        }, 500
        # ==========================================================
# NOVA ADS - SYSTEME PUBLICITAIRE SEPARE
# ==========================================================

# Mot de passe NovaAds
CODE_ADS = "3004"


# ==========================================================
# PROTECTION NOVA ADS
# ==========================================================

def ads_required(f):

    @wraps(f)
    def wrapper(*args, **kwargs):

        if not session.get("ads_admin"):
            return redirect(
                url_for("ads_login")
            )

        return f(*args, **kwargs)

    return wrapper


# ==========================================================
# CONNEXION NOVA ADS
# ==========================================================

@app.route(
    "/ads-login",
    methods=["GET", "POST"]
)
def ads_login():

    if session.get("ads_admin"):

        return redirect(
            url_for("ads")
        )

    erreur = None

    if request.method == "POST":

        code = request.form.get(
            "code",
            ""
        ).strip()

        if code == CODE_ADS:

            session["ads_admin"] = True

            return redirect(
                url_for("ads")
            )

        erreur = (
            "Code NovaAds incorrect."
        )

    return render_template(
        "ads-login.html",
        erreur=erreur
    )


# ==========================================================
# DECONNEXION NOVA ADS
# ==========================================================

@app.route("/ads-logout")
def ads_logout():

    session.pop(
        "ads_admin",
        None
    )

    return redirect(
        url_for("ads_login")
    )


# ==========================================================
# PAGE PRINCIPALE NOVA ADS
# ==========================================================

@app.route("/ads")
@ads_required
def ads():

    try:

        resultat = (
            supabase
            .table("publicites")
            .select("*")
            .order("id", desc=True)
            .execute()
        )

        publicites = (
            resultat.data or []
        )

    except Exception as e:

        print(
            "ERREUR NOVA ADS :",
            str(e)
        )

        publicites = []

    return render_template(
        "ads.html",
        publicites=publicites
    )


# ==========================================================
# AJOUTER UNE PUBLICITE
# ==========================================================

@app.route(
    "/ads/ajouter",
    methods=["POST"]
)
@ads_required
def ads_ajouter():

    nom = request.form.get(
        "nom",
        ""
    ).strip()

    code = request.form.get(
        "code",
        ""
    ).strip()

    emplacement = request.form.get(
        "emplacement",
        ""
    ).strip()

    type_pub = request.form.get(
        "type",
        "image"
    ).strip()

    contenu_url = request.form.get(
        "contenu_url",
        ""
    ).strip()

    lien = request.form.get(
        "lien",
        ""
    ).strip()

    if not nom or not code or not emplacement:

        return (
            "Nom, code et emplacement sont obligatoires.",
            400
        )

    try:

        # ==================================================
        # VERIFIER SI L'EMPLACEMENT EST DEJA OCCUPE
        # ==================================================

        existant = (
            supabase
            .table("publicites")
            .select("id, nom, actif")
            .eq(
                "emplacement",
                emplacement
            )
            .eq(
                "actif",
                True
            )
            .limit(1)
            .execute()
        )

        if existant.data:

            return (
                "Cet emplacement publicitaire est déjà occupé. "
                "La publicité existante n'a pas été modifiée.",
                409
            )


        # ==================================================
        # VERIFIER LE CODE
        # ==================================================

        code_existant = (
            supabase
            .table("publicites")
            .select("id")
            .eq(
                "code",
                code
            )
            .limit(1)
            .execute()
        )

        if code_existant.data:

            return (
                "Ce code publicitaire existe déjà.",
                409
            )


        # ==================================================
        # CREATION
        # ==================================================

        supabase.table(
            "publicites"
        ).insert({

            "nom":
                nom,

            "code":
                code,

            "emplacement":
                emplacement,

            "type":
                type_pub,

            "contenu_url":
                contenu_url,

            "lien":
                lien,

            "actif":
                True,

            "impressions":
                0,

            "clics":
                0

        }).execute()


    except Exception as e:

        print(
            "ERREUR AJOUT PUBLICITE :",
            str(e)
        )

        return (
            "Erreur lors de l'ajout de la publicité.",
            500
        )


    return redirect(
        url_for("ads")
    )


# ==========================================================
# ACTIVER / DESACTIVER UNE PUBLICITE
# ==========================================================

@app.route(
    "/ads/toggle/<int:pub_id>",
    methods=["POST"]
)
@ads_required
def ads_toggle(pub_id):

    try:

        resultat = (
            supabase
            .table("publicites")
            .select("*")
            .eq("id", pub_id)
            .limit(1)
            .execute()
        )

        publicites = resultat.data or []

        if not publicites:

            abort(404)

        publicite = publicites[0]

        nouvel_etat = not bool(
            publicite.get("actif")
        )


        # ==================================================
        # SI ON ACTIVE UNE PUB
        # VERIFIER QUE L'EMPLACEMENT EST LIBRE
        # ==================================================

        if nouvel_etat:

            emplacement = publicite.get(
                "emplacement"
            )

            autre_pub = (
                supabase
                .table("publicites")
                .select("id")
                .eq(
                    "emplacement",
                    emplacement
                )
                .eq(
                    "actif",
                    True
                )
                .neq(
                    "id",
                    pub_id
                )
                .limit(1)
                .execute()
            )

            if autre_pub.data:

                return (
                    "Impossible d'activer cette publicité : "
                    "l'emplacement est déjà occupé.",
                    409
                )


        supabase.table(
            "publicites"
        ).update({

            "actif":
                nouvel_etat

        }).eq(
            "id",
            pub_id
        ).execute()


    except Exception as e:

        print(
            "ERREUR ACTIVATION PUBLICITE :",
            str(e)
        )

        return (
            "Erreur lors de la modification de la publicité.",
            500
        )


    return redirect(
        url_for("ads")
    )


# ==========================================================
# SUPPRIMER UNE PUBLICITE
# ==========================================================

@app.route(
    "/ads/supprimer/<int:pub_id>",
    methods=["POST"]
)
@ads_required
def ads_supprimer(pub_id):

    try:

        supabase.table(
            "publicites"
        ).delete().eq(
            "id",
            pub_id
        ).execute()


    except Exception as e:

        print(
            "ERREUR SUPPRESSION PUBLICITE :",
            str(e)
        )

        return (
            "Erreur lors de la suppression.",
            500
        )


    return redirect(
        url_for("ads")
    )


# ==========================================================
# COMPTER UNE IMPRESSION
# ==========================================================

@app.route(
    "/api/ads/impression/<int:pub_id>",
    methods=["POST"]
)
def ads_impression(pub_id):

    try:

        resultat = (
            supabase
            .table("publicites")
            .select("impressions, actif")
            .eq("id", pub_id)
            .limit(1)
            .execute()
        )

        publicites = resultat.data or []

        if not publicites:

            return {
                "success": False
            }, 404

        publicite = publicites[0]

        if not publicite.get("actif"):

            return {
                "success": False
            }


        impressions = (
            publicite.get("impressions")
            or 0
        )

        supabase.table(
            "publicites"
        ).update({

            "impressions":
                impressions + 1

        }).eq(
            "id",
            pub_id
        ).execute()


        return {
            "success": True
        }


    except Exception as e:

        print(
            "ERREUR IMPRESSION PUBLICITE :",
            str(e)
        )

        return {
            "success": False
        }, 500


# ==========================================================
# COMPTER UN CLIC
# ==========================================================

@app.route(
    "/api/ads/clic/<int:pub_id>",
    methods=["POST"]
)
def ads_clic(pub_id):

    try:

        resultat = (
            supabase
            .table("publicites")
            .select("clics, actif")
            .eq("id", pub_id)
            .limit(1)
            .execute()
        )

        publicites = resultat.data or []

        if not publicites:

            return {
                "success": False
            }, 404

        publicite = publicites[0]

        if not publicite.get("actif"):

            return {
                "success": False
            }


        clics = (
            publicite.get("clics")
            or 0
        )

        supabase.table(
            "publicites"
        ).update({

            "clics":
                clics + 1

        }).eq(
            "id",
            pub_id
        ).execute()


        return {
            "success": True
        }


    except Exception as e:

        print(
            "ERREUR CLIC PUBLICITE :",
            str(e)
        )

        return {
            "success": False
        }, 500


# ==========================
# LANCEMENT
# ==========================

if __name__ == "__main__":

    print("")
    print("==============================")
    print("🎮 GAME STORE")
    print("==============================")
    print("")

    print("☁️ Base de données :")
    print("Supabase")
    print("")

    print("📸 Images :")
    print("Cloudinary")
    print("")

    print("🔐 Administration :")
    print("/login")
    print("")

    print("🏠 Accueil :")
    print("/")
    print("")

    print("==============================")
    print("🚀 Serveur démarré")
    print("==============================")
    print("")

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
)
