# ==========================================================
# GAME STORE - APP.PY (NOVAGAMING)
# ==========================================================

import os
import re
import json
from datetime import datetime, timezone
from functools import wraps

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
    send_from_directory,
    flash,
    jsonify
)

from supabase import create_client, Client

# ==========================
# FIREBASE CLOUD MESSAGING
# ==========================
import firebase_admin
from firebase_admin import credentials, messaging

# ==========================
# INITIALISATION FIREBASE
# ==========================
if not firebase_admin._apps:
    firebase_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
    if not firebase_json:
        print("⚠️ FIREBASE_SERVICE_ACCOUNT n'est pas configurée.")
    else:
        try:
            service_account = json.loads(firebase_json)
            cred = credentials.Certificate(service_account)
            firebase_admin.initialize_app(cred)
            print("✅ Firebase Cloud Messaging initialisé.")
        except Exception as e:
            print("❌ ERREUR INITIALISATION FIREBASE :", str(e))


# ==========================
# ENVOYER UNE NOTIFICATION PUSH
# ==========================
def envoyer_notification_push(token, titre, message, image_url=None):
    if not token:
        return False
    try:
        notification = messaging.Notification(
            title=titre,
            body=message
        )
        webpush_notification = messaging.WebpushNotification(
            title=titre,
            body=message,
            image=image_url
        )
        webpush = messaging.WebpushConfig(
            notification=webpush_notification
        )
        message_firebase = messaging.Message(
            notification=notification,
            token=token,
            webpush=webpush
        )
        resultat = messaging.send(message_firebase)
        print("✅ Notification Firebase envoyée :", resultat)
        return True
    except Exception as e:
        print("❌ ERREUR NOTIFICATION FIREBASE :", str(e))
        return False


# ==========================
# CONFIGURATION FLASK
# ==========================
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "CHANGE-MOI-PAR-UNE-CLE-SECRETE")


# ==========================
# CODE ADMIN
# ==========================
CODE_ADMIN = "3004"


# ==========================
# SUPABASE
# ==========================
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)

# ==========================
# CLOUDINARY
# ==========================
cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME", "zgp2vxel"),
    api_key=os.environ.get("CLOUDINARY_API_KEY", "357264626165689"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET", "CkGRcrzSyk4gR-PIA3WC5jMItFI")
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

    extensions_autorisees = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    extension = os.path.splitext(fichier.filename)[1].lower()

    if extension not in extensions_autorisees:
        print("Extension non autorisée :", extension)
        return None

    try:
        resultat = cloudinary.uploader.upload(
            fichier,
            folder="novagaming/jeux",
            resource_type="image"
        )
        image_url = resultat.get("secure_url")
        if not image_url:
            print("Cloudinary n'a pas retourné d'URL.")
            return None
        print("IMAGE CLOUDINARY :", image_url)
        return image_url
    except Exception as e:
        print("ERREUR UPLOAD CLOUDINARY :", str(e))
        return None


# ==========================
# PROTECTION ADMIN
# ==========================
def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("login"))
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
        print("ERREUR SUPABASE ACCUEIL :", str(e))
        jeux = []

    return render_template("index.html", jeux=jeux)


# ==========================
# RECHERCHE
# ==========================
@app.route("/recherche")
def recherche():
    q = request.args.get("q", "").strip()
    try:
        requete = supabase.table("jeux").select("*")
        if q:
            resultat = requete.or_(
                f"nom.ilike.%{q}%,"
                f"console.ilike.%{q}%,"
                f"description.ilike.%{q}%"
            ).order("id", desc=True).execute()
        else:
            resultat = requete.order("id", desc=True).execute()
        jeux = resultat.data or []
    except Exception as e:
        print("ERREUR SUPABASE RECHERCHE :", str(e))
        jeux = []

    return render_template("index.html", jeux=jeux, recherche=q)


# ==========================
# PAGE D'UN JEU
# ==========================
@app.route("/jeu/<int:jeu_id>")
def jeu(jeu_id):
    try:
        # RÉCUPÉRER LE JEU
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

        # RÉCUPÉRER LES COMMENTAIRES
        resultat_commentaires = (
            supabase
            .table("commentaires")
            .select("*")
            .eq("jeu_id", jeu_id)
            .order("id", desc=True)
            .execute()
        )
        commentaires = resultat_commentaires.data or []

        # RÉCUPÉRER LES PUBLICITÉS NOVA ADS
        resultat_ads = (
            supabase
            .table("publicites")
            .select("*")
            .eq("actif", True)
            .execute()
        )
        publicites = resultat_ads.data or []

        nova_ads = {}
        for pub in publicites:
            emplacement = pub.get("emplacement")
            if emplacement:
                nova_ads[emplacement] = pub

    except Exception as e:
        print("ERREUR SUPABASE PAGE JEU :", str(e))
        abort(500)

    return render_template(
        "jeu.html",
        jeu=jeu_data,
        commentaires=commentaires,
        nova_ads=nova_ads
    )


# ==========================
# TELECHARGEMENT
# ==========================
@app.route("/telecharger/<int:jeu_id>")
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
            return "Lien de téléchargement indisponible.", 404

        ancien_compteur = jeu_data.get("telechargements") or 0
        supabase.table("jeux").update({
            "telechargements": ancien_compteur + 1
        }).eq("id", jeu_id).execute()

    except Exception as e:
        print("ERREUR TELECHARGEMENT :", str(e))
        return "Une erreur est survenue.", 500

    return redirect(lien)


# ==========================
# COMMENTAIRES
# ==========================
@app.route("/commentaire/<int:jeu_id>", methods=["POST"])
def commentaire(jeu_id):
    pseudo = request.form.get("pseudo", "").strip()
    texte = request.form.get("commentaire", "").strip()

    if not texte:
        return redirect(url_for("jeu", jeu_id=jeu_id))

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

        supabase.table("commentaires").insert({
            "jeu_id": jeu_id,
            "pseudo": pseudo,
            "commentaire": texte
        }).execute()

        supabase.table("notifications").insert({
            "titre": "Nouveau commentaire 💬",
            "message": f"{pseudo} a commenté un jeu.",
            "lu": 0
        }).execute()

    except Exception as e:
        print("ERREUR COMMENTAIRE :", str(e))

    return redirect(url_for("jeu", jeu_id=jeu_id))


# ==========================
# CONNEXION ADMIN
# ==========================
@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("admin"):
        return redirect(url_for("admin"))

    erreur = None
    if request.method == "POST":
        code = request.form.get("code", "").strip()
        if not code:
            code = request.form.get("password", "").strip()

        if code == CODE_ADMIN:
            session["admin"] = True
            return redirect(url_for("admin"))

        erreur = "Code administrateur incorrect."

    return render_template("login.html", erreur=erreur)


# ==========================
# DECONNEXION
# ==========================
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("accueil"))


# ==========================
# ADMINISTRATION
# ==========================
@app.route("/admin")
@admin_required
def admin():
    try:
        resultat_jeux = (
            supabase
            .table("jeux")
            .select("*")
            .order("id", desc=True)
            .execute()
        )
        jeux = resultat_jeux.data or []

        resultat_total_jeux = supabase.table("jeux").select("id", count="exact").execute()
        total_jeux = resultat_total_jeux.count or 0

        resultat_telechargements = supabase.table("jeux").select("telechargements").execute()
        total_telechargements = sum(j.get("telechargements") or 0 for j in (resultat_telechargements.data or []))

        resultat_total_commentaires = supabase.table("commentaires").select("id", count="exact").execute()
        total_commentaires = resultat_total_commentaires.count or 0

        resultat_commentaires = (
            supabase
            .table("commentaires")
            .select("*")
            .order("id", desc=True)
            .limit(30)
            .execute()
        )
        commentaires_admin = resultat_commentaires.data or []

        resultat_notifications = (
            supabase
            .table("notifications")
            .select("*")
            .order("id", desc=True)
            .limit(10)
            .execute()
        )
        notifications_admin = resultat_notifications.data or []

    except Exception as e:
        print("ERREUR ADMIN SUPABASE :", str(e))
        jeux = []
        total_jeux = 0
        total_telechargements = 0
        total_commentaires = 0
        commentaires_admin = []
        notifications_admin = []

    return render_template(
        "admin.html",
        jeux=jeux,
        total_jeux=total_jeux,
        total_telechargements=total_telechargements,
        total_commentaires=total_commentaires,
        commentaires_admin=commentaires_admin,
        notifications_admin=notifications_admin
    )


# ==========================
# AJOUTER UN JEU MANUEL
# ==========================
@app.route("/admin/ajouter", methods=["POST"])
@admin_required
def ajouter():
    nom = request.form.get("nom", "").strip()
    console = request.form.get("console", "").strip()
    description = request.form.get("description", "").strip()
    taille = request.form.get("taille", "").strip()
    version = request.form.get("version", "").strip()
    langue = request.form.get("langue", "").strip()
    couverture = request.form.get("couverture", "").strip()
    lien = request.form.get("lien", "").strip()

    if not nom:
        return "Le nom du jeu est obligatoire.", 400
    if not lien:
        return "Le lien de téléchargement est obligatoire.", 400

    couverture_file = request.files.get("couverture_file")
    if couverture_file and couverture_file.filename:
        image_couverture = enregistrer_image(couverture_file, "couverture")
        if image_couverture:
            couverture = image_couverture

    fichiers_images = request.files.getlist("images")
    images = []
    for fichier in fichiers_images[:10]:
        if not fichier or not fichier.filename:
            continue
        image_url = enregistrer_image(fichier, "galerie")
        if image_url:
            images.append(image_url)

    while len(images) < 10:
        images.append("")

    try:
        supabase.table("jeux").insert({
            "nom": nom,
            "console": console,
            "description": description,
            "taille": taille,
            "version": version,
            "langue": langue,
            "couverture": couverture,
            "image1": images[0],
            "image2": images[1],
            "image3": images[2],
            "image4": images[3],
            "image5": images[4],
            "image6": images[5],
            "image7": images[6],
            "image8": images[7],
            "image9": images[8],
            "image10": images[9],
            "lien": lien,
            "telechargements": 0,
            "date_ajout": datetime.now(timezone.utc).isoformat()
        }).execute()

        supabase.table("notifications").insert({
            "titre": "Nouveau jeu disponible 🎮",
            "message": f"{nom} vient d'être ajouté au catalogue.",
            "lu": 0
        }).execute()

        try:
            resultat_tokens = supabase.table("tokens_fcm").select("token").execute()
            for element in (resultat_tokens.data or []):
                token = element.get("token")
                if token:
                    envoyer_notification_push(
                        token,
                        "Nouveau jeu disponible 🎮",
                        f"{nom} vient d'être ajouté au catalogue.",
                        couverture
                    )
        except Exception as e:
            print("ERREUR PUSH FIREBASE :", str(e))

    except Exception as e:
        print("ERREUR AJOUT JEU SUPABASE :", str(e))
        return "Erreur lors de l'ajout du jeu.", 500

    return redirect(url_for("admin"))


# ==========================
# MODIFIER UN JEU
# ==========================
@app.route("/admin/modifier/<int:jeu_id>", methods=["GET", "POST"])
@admin_required
def modifier(jeu_id):
    try:
        resultat = supabase.table("jeux").select("*").eq("id", jeu_id).limit(1).execute()
        jeux = resultat.data or []
        if not jeux:
            abort(404)
        jeu_data = jeux[0]
    except Exception as e:
        print("ERREUR RECUPERATION JEU :", str(e))
        abort(500)

    if request.method == "GET":
        return render_template("modifier.html", jeu=jeu_data)

    nom = request.form.get("nom", "").strip()
    console = request.form.get("console", "").strip()
    description = request.form.get("description", "").strip()
    taille = request.form.get("taille", "").strip()
    version = request.form.get("version", "").strip()
    langue = request.form.get("langue", "").strip()
    couverture = request.form.get("couverture", "").strip()
    lien = request.form.get("lien", "").strip()

    if not nom:
        return "Le nom du jeu est obligatoire.", 400
    if not lien:
        return "Le lien de téléchargement est obligatoire.", 400

    couverture_file = request.files.get("couverture_file")
    if couverture_file and couverture_file.filename:
        nouvelle_couverture = enregistrer_image(couverture_file, "couverture")
        if nouvelle_couverture:
            couverture = nouvelle_couverture
    elif not couverture:
        couverture = jeu_data.get("couverture") or ""

    anciennes_images = [jeu_data.get(f"image{i}") or "" for i in range(1, 11)]
    fichiers_images = request.files.getlist("images")
    nouvelles_images = []

    for fichier in fichiers_images[:10]:
        if not fichier or not fichier.filename:
            continue
        image_url = enregistrer_image(fichier, "galerie")
        if image_url:
            nouvelles_images.append(image_url)

    if nouvelles_images:
        images = nouvelles_images
        while len(images) < 10:
            images.append("")
    else:
        images = anciennes_images

    try:
        supabase.table("jeux").update({
            "nom": nom,
            "console": console,
            "description": description,
            "taille": taille,
            "version": version,
            "langue": langue,
            "couverture": couverture,
            "image1": images[0],
            "image2": images[1],
            "image3": images[2],
            "image4": images[3],
            "image5": images[4],
            "image6": images[5],
            "image7": images[6],
            "image8": images[7],
            "image9": images[8],
            "image10": images[9],
            "lien": lien
        }).eq("id", jeu_id).execute()

        supabase.table("notifications").insert({
            "titre": "Jeu modifié ✏️",
            "message": f"{nom} a été modifié.",
            "lu": 0
        }).execute()

        try:
            resultat_tokens = supabase.table("tokens_fcm").select("token").execute()
            for element in (resultat_tokens.data or []):
                token = element.get("token")
                if token:
                    envoyer_notification_push(
                        token,
                        "Jeu modifié ✏️",
                        f"{nom} a été modifié.",
                        couverture
                    )
        except Exception as e:
            print("ERREUR PUSH MODIFICATION :", str(e))

    except Exception as e:
        print("ERREUR MODIFICATION SUPABASE :", str(e))
        return "Erreur lors de la modification.", 500

    return redirect(url_for("admin"))


# ==========================
# SUPPRIMER UN JEU
# ==========================
@app.route("/admin/supprimer/<int:jeu_id>")
@admin_required
def supprimer(jeu_id):
    try:
        resultat = supabase.table("jeux").select("*").eq("id", jeu_id).limit(1).execute()
        jeux = resultat.data or []
        if not jeux:
            abort(404)
        jeu_data = jeux[0]

        supabase.table("commentaires").delete().eq("jeu_id", jeu_id).execute()
        supabase.table("favoris").delete().eq("jeu_id", jeu_id).execute()
        supabase.table("vues").delete().eq("jeu_id", jeu_id).execute()
        supabase.table("jeux").delete().eq("id", jeu_id).execute()

        nom_jeu = jeu_data.get("nom", "Le jeu")
        couverture_jeu = jeu_data.get("couverture")

        supabase.table("notifications").insert({
            "titre": "Jeu supprimé 🗑️",
            "message": f"{nom_jeu} a été supprimé du catalogue.",
            "lu": 0
        }).execute()

        try:
            resultat_tokens = supabase.table("tokens_fcm").select("token").execute()
            for element in (resultat_tokens.data or []):
                token = element.get("token")
                if token:
                    envoyer_notification_push(
                        token,
                        "Jeu supprimé 🗑️",
                        f"{nom_jeu} a été supprimé du catalogue.",
                        couverture_jeu
                    )
        except Exception as e:
            print("ERREUR PUSH SUPPRESSION :", str(e))

    except Exception as e:
        print("ERREUR SUPPRESSION JEU SUPABASE :", str(e))
        return "Erreur lors de la suppression du jeu.", 500

    return redirect(url_for("admin"))


# ==========================
# SUPPRIMER UN COMMENTAIRE
# ==========================
@app.route("/admin/commentaire/supprimer/<int:commentaire_id>")
@admin_required
def supprimer_commentaire(commentaire_id):
    try:
        supabase.table("commentaires").delete().eq("id", commentaire_id).execute()
    except Exception as e:
        print("ERREUR SUPPRESSION COMMENTAIRE :", str(e))
        return "Erreur lors de la suppression.", 500

    return redirect(url_for("admin"))


# ==========================
# FAVORIS
# ==========================
@app.route("/favori/<int:jeu_id>")
def favori(jeu_id):
    ip = request.remote_addr
    try:
        resultat_jeu = supabase.table("jeux").select("id").eq("id", jeu_id).limit(1).execute()
        if not resultat_jeu.data:
            abort(404)

        resultat_favori = supabase.table("favoris").select("id").eq("jeu_id", jeu_id).eq("ip", ip).limit(1).execute()

        if resultat_favori.data:
            supabase.table("favoris").delete().eq("jeu_id", jeu_id).eq("ip", ip).execute()
        else:
            supabase.table("favoris").insert({"jeu_id": jeu_id, "ip": ip}).execute()

    except Exception as e:
        print("ERREUR FAVORI SUPABASE :", str(e))
        return "Erreur lors de la gestion du favori.", 500

    return redirect(url_for("jeu", jeu_id=jeu_id))


# ==========================
# NOTIFICATIONS
# ==========================
@app.route("/notifications")
def notifications():
    try:
        resultat = supabase.table("notifications").select("*").order("id", desc=True).execute()
        liste = resultat.data or []
    except Exception as e:
        print("ERREUR NOTIFICATIONS SUPABASE :", str(e))
        liste = []

    return render_template("notifications.html", notifications=liste)


# ==========================
# MARQUER LES NOTIFICATIONS COMME LUES
# ==========================
@app.route("/notifications/lues", methods=["POST"])
def notifications_lues():
    try:
        supabase.table("notifications").update({"lu": 1}).eq("lu", 0).execute()
    except Exception as e:
        print("ERREUR NOTIFICATIONS LUES :", str(e))
        return "Erreur lors de la mise à jour.", 500

    return redirect(url_for("notifications"))


# ==========================
# JEUX POPULAIRES
# ==========================
@app.route("/populaires")
def populaires():
    try:
        resultat = supabase.table("jeux").select("*").order("telechargements", desc=True).limit(20).execute()
        jeux = resultat.data or []
    except Exception as e:
        print("ERREUR JEUX POPULAIRES :", str(e))
        jeux = []

    return render_template("index.html", jeux=jeux, titre="🔥 Jeux populaires")


# ==========================
# NOUVEAUTÉS
# ==========================
@app.route("/nouveautes")
def nouveautes():
    try:
        resultat = supabase.table("jeux").select("*").order("id", desc=True).limit(20).execute()
        jeux = resultat.data or []
    except Exception as e:
        print("ERREUR NOUVEAUTES :", str(e))
        jeux = []

    return render_template("index.html", jeux=jeux, titre="🆕 Nouveautés")


# ==========================
# COMPTEUR DE VUES
# ==========================
@app.before_request
def compteur_vues():
    if request.endpoint != "jeu" or not request.view_args:
        return

    jeu_id = request.view_args.get("jeu_id")
    if not jeu_id:
        return

    ip = request.remote_addr
    try:
        resultat = (
            supabase
            .table("vues")
            .select("id,date")
            .eq("jeu_id", jeu_id)
            .eq("ip", ip)
            .order("date", desc=True)
            .limit(1)
            .execute()
        )
        vues = resultat.data or []
        ajouter_vue = True

        if vues:
            date_vue = vues[0].get("date")
            if date_vue:
                try:
                    date_vue = date_vue.replace("Z", "+00:00")
                    date_vue = datetime.fromisoformat(date_vue)
                    maintenant = datetime.now(timezone.utc)
                    if (maintenant - date_vue).total_seconds() < 1800:
                        ajouter_vue = False
                except Exception:
                    ajouter_vue = True

        if ajouter_vue:
            supabase.table("vues").insert({"jeu_id": jeu_id, "ip": ip}).execute()

    except Exception as e:
        print("ERREUR COMPTEUR VUES :", str(e))


# ==========================
# NOMBRE DE FAVORIS
# ==========================
@app.context_processor
def fonctions_globales():
    def nombre_favoris(jeu_id):
        try:
            resultat = supabase.table("favoris").select("id", count="exact").eq("jeu_id", jeu_id).execute()
            return resultat.count or 0
        except Exception as e:
            print("ERREUR NOMBRE FAVORIS :", str(e))
            return 0

    return {"nombre_favoris": nombre_favoris}


# ==========================
# STATISTIQUES GLOBALES
# ==========================
@app.context_processor
def statistiques_globales():
    try:
        res_com = supabase.table("commentaires").select("id", count="exact").execute()
        commentaires = res_com.count or 0

        res_jeux = supabase.table("jeux").select("id", count="exact").execute()
        jeux = res_jeux.count or 0

        res_dl = supabase.table("jeux").select("telechargements").execute()
        telechargements = sum(j.get("telechargements") or 0 for j in (res_dl.data or []))

        res_notif = supabase.table("notifications").select("id", count="exact").eq("lu", 0).execute()
        notifications_non_lues = res_notif.count or 0

    except Exception as e:
        print("ERREUR STATISTIQUES SUPABASE :", str(e))
        commentaires, jeux, telechargements, notifications_non_lues = 0, 0, 0, 0

    return {
        "total_commentaires": commentaires,
        "total_jeux": jeux,
        "total_telechargements": telechargements,
        "notifications_non_lues": notifications_non_lues
    }


# ==========================
# PAGE 404 & 500
# ==========================
@app.errorhandler(404)
def page_introuvable(error):
    return """
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <title>404 - Page introuvable</title>
        <style>
            body { margin: 0; min-height: 100vh; display: flex; align-items: center; justify-content: center; font-family: Arial, sans-serif; background: #0f141c; color: white; text-align: center; }
            .error-box { padding: 40px 25px; max-width: 500px; }
            h1 { font-size: 80px; margin: 0; }
            p { color: #9aa8ba; }
            a { display: inline-block; margin-top: 20px; padding: 12px 20px; border-radius: 10px; background: #4da3ff; color: white; text-decoration: none; font-weight: bold; }
        </style>
    </head>
    <body>
        <div class="error-box">
            <h1>404</h1>
            <h2>Page introuvable</h2>
            <p>La page que tu recherches n'existe pas.</p>
            <a href="/">🏠 Retour à l'accueil</a>
        </div>
    </body>
    </html>
    """, 404


@app.errorhandler(500)
def erreur_serveur(error):
    return """
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <title>500 - Erreur serveur</title>
        <style>
            body { margin: 0; min-height: 100vh; display: flex; align-items: center; justify-content: center; font-family: Arial, sans-serif; background: #0f141c; color: white; text-align: center; }
            .error-box { padding: 40px 25px; max-width: 500px; }
            h1 { font-size: 70px; margin: 0; }
            p { color: #9aa8ba; }
            a { display: inline-block; margin-top: 20px; padding: 12px 20px; border-radius: 10px; background: #4da3ff; color: white; text-decoration: none; font-weight: bold; }
        </style>
    </head>
    <body>
        <div class="error-box">
            <h1>500</h1>
            <h2>Erreur serveur</h2>
            <p>Une erreur est survenue. Réessaie dans quelques instants.</p>
            <a href="/">🏠 Retour à l'accueil</a>
        </div>
    </body>
    </html>
    """, 500


# ==========================
# ROBOTS.TXT & SITEMAP.XML
# ==========================
@app.route("/robots.txt")
def robots():
    return send_from_directory(".", "robots.txt")


@app.route("/sitemap.xml")
def sitemap():
    return send_from_directory(".", "sitemap.xml")


# ==========================
# TEST SUPABASE
# ==========================
@app.route("/test-supabase")
@admin_required
def test_supabase():
    try:
        resultat = supabase.table("jeux").select("id").limit(1).execute()
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


# ==========================================================
# TOKEN FCM
# ==========================================================
@app.route("/api/token-fcm", methods=["POST"])
def enregistrer_token_fcm():
    donnees = request.get_json(silent=True) or {}
    token = str(donnees.get("token", "")).strip()

    if not token:
        return {"success": False, "message": "Token manquant."}, 400

    try:
        supabase.table("tokens_fcm").upsert({"token": token}, on_conflict="token").execute()
        return {"success": True}
    except Exception as e:
        print("ERREUR TOKEN FCM :", str(e))
        return {"success": False, "message": str(e)}, 500


# ==========================================================
# ANALYTICS
# ==========================================================
def enregistrer_statistique(type_evenement, page=None, jeu_id=None, secondes=None):
    try:
        ip = request.headers.get("X-Forwarded-For")
        if ip:
            ip = ip.split(",")[0].strip()
        else:
            ip = request.remote_addr

        user_agent = request.headers.get("User-Agent", "")
        date_actuelle = datetime.now(timezone.utc).isoformat()

        donnees = {
            "type_evenement": type_evenement,
            "page": page,
            "jeu_id": jeu_id,
            "ip": ip,
            "user_agent": user_agent,
            "date": date_actuelle
        }
        if secondes is not None:
            donnees["secondes"] = int(secondes)

        supabase.table("analytics").insert(donnees).execute()
        return True
    except Exception as erreur:
        print("❌ ERREUR ANALYTICS :", repr(erreur))
        return False


@app.route("/api/analytics/visite", methods=["POST"])
def analytics_visite():
    try:
        donnees = request.get_json(silent=True) or {}
        page = str(donnees.get("page", "/")).strip() or "/"
        succes = enregistrer_statistique(type_evenement="visite", page=page)
        if not succes:
            return {"success": False, "message": "Impossible d'enregistrer la visite."}, 500
        return {"success": True, "page": page}, 200
    except Exception as erreur:
        return {"success": False, "message": str(erreur)}, 500


@app.route("/api/analytics/temps", methods=["POST"])
def analytics_temps():
    donnees = request.get_json(silent=True) or {}
    page = str(donnees.get("page", "/")).strip() or "/"
    secondes = donnees.get("secondes", 0)
    try:
        secondes = int(secondes)
    except:
        secondes = 0
    secondes = max(0, min(secondes, 86400))
    enregistrer_statistique(type_evenement="temps", page=page, secondes=secondes)
    return {"success": True}


@app.route("/api/admin/statistiques")
@admin_required
def statistiques_admin():
    try:
        resultat = supabase.table("analytics").select("*").execute()
        donnees = resultat.data or []

        visites = [x for x in donnees if x.get("type_evenement") == "visite"]
        visiteurs_total = len(visites)

        ips = {visite.get("ip") for visite in visites if visite.get("ip")}
        visiteurs_uniques = len(ips)

        pages_vues = {}
        for visite in visites:
            page = visite.get("page") or "/"
            pages_vues[page] = pages_vues.get(page, 0) + 1

        pages_populaires = sorted(pages_vues.items(), key=lambda x: x[1], reverse=True)[:10]

        temps = [x for x in donnees if x.get("type_evenement") == "temps"]
        temps_total = sum(int(element.get("secondes") or 0) for element in temps)
        temps_moyen = (temps_total / len(temps)) if temps else 0

        maintenant = datetime.now(timezone.utc)
        utilisateurs_actifs = set()
        for visite in visites:
            date_visite = visite.get("date")
            if not date_visite:
                continue
            try:
                date_obj = datetime.fromisoformat(date_visite.replace("Z", "+00:00"))
                if date_obj.tzinfo is None:
                    date_obj = date_obj.replace(tzinfo=timezone.utc)
                if 0 <= (maintenant - date_obj).total_seconds() <= 300:
                    if visite.get("ip"):
                        utilisateurs_actifs.add(visite.get("ip"))
            except Exception:
                continue

        return {
            "success": True,
            "visiteurs_total": visiteurs_total,
            "visiteurs_uniques": visiteurs_uniques,
            "pages_vues": sum(pages_vues.values()),
            "pages_populaires": [{"page": page, "visites": nombre} for page, nombre in pages_populaires],
            "utilisateurs_actifs": len(utilisateurs_actifs),
            "temps_total_secondes": temps_total,
            "temps_moyen_secondes": round(temps_moyen, 1)
        }
    except Exception as e:
        print("ERREUR STATISTIQUES ADMIN :", str(e))
        return {"success": False, "message": str(e)}, 500


@app.route("/api/admin/telechargements")
@admin_required
def statistiques_telechargements():
    try:
        resultat = supabase.table("jeux").select("id,nom,telechargements").order("telechargements", desc=True).execute()
        jeux = resultat.data or []
        total = sum(int(j.get("telechargements") or 0) for j in jeux)
        return {"success": True, "total": total, "jeux": jeux}
    except Exception as e:
        print("ERREUR STATS TELECHARGEMENTS :", str(e))
        return {"success": False, "message": str(e)}, 500


# ==========================================================
# NOVA ADS - SYSTEME PUBLICITAIRE
# ==========================================================
CODE_ADS = "3004"

def ads_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("ads_admin"):
            return redirect(url_for("ads_login"))
        return f(*args, **kwargs)
    return wrapper


@app.route("/ads-login", methods=["GET", "POST"])
def ads_login():
    if session.get("ads_admin"):
        return redirect(url_for("ads"))

    erreur = None
    if request.method == "POST":
        code = request.form.get("code", "").strip()
        if code == CODE_ADS:
            session["ads_admin"] = True
            return redirect(url_for("ads"))
        erreur = "Code NovaAds incorrect."

    return render_template("ads-login.html", erreur=erreur)


@app.route("/ads-logout")
def ads_logout():
    session.pop("ads_admin", None)
    return redirect(url_for("ads_login"))


@app.route("/ads")
@ads_required
def ads():
    try:
        resultat = supabase.table("publicites").select("*").order("id", desc=True).execute()
        publicites = resultat.data or []
    except Exception as e:
        print("ERREUR NOVA ADS :", str(e))
        publicites = []

    return render_template("ads.html", publicites=publicites)


@app.route("/ads/ajouter", methods=["POST"])
@ads_required
def ads_ajouter():
    nom = request.form.get("nom", "").strip()
    code = request.form.get("code", "").strip()
    emplacement = request.form.get("emplacement", "").strip()
    type_pub = request.form.get("type", "image").strip()
    contenu_url = request.form.get("contenu_url", "").strip()
    lien = request.form.get("lien", "").strip()

    if not nom or not code or not emplacement:
        return "Nom, code et emplacement sont obligatoires.", 400

    try:
        existant = supabase.table("publicites").select("id, nom, actif").eq("emplacement", emplacement).eq("actif", True).limit(1).execute()
        if existant.data:
            return "Cet emplacement publicitaire est déjà occupé.", 409

        code_existant = supabase.table("publicites").select("id").eq("code", code).limit(1).execute()
        if code_existant.data:
            return "Ce code publicitaire existe déjà.", 409

        supabase.table("publicites").insert({
            "nom": nom,
            "code": code,
            "emplacement": emplacement,
            "type": type_pub,
            "contenu_url": contenu_url,
            "lien": lien,
            "actif": True,
            "impressions": 0,
            "clics": 0
        }).execute()
    except Exception as e:
        print("ERREUR AJOUT PUBLICITE :", str(e))
        return "Erreur lors de l'ajout de la publicité.", 500

    return redirect(url_for("ads"))


@app.route("/ads/toggle/<int:pub_id>", methods=["POST"])
@ads_required
def ads_toggle(pub_id):
    try:
        resultat = supabase.table("publicites").select("*").eq("id", pub_id).limit(1).execute()
        publicites = resultat.data or []
        if not publicites:
            abort(404)

        publicite = publicites[0]
        nouvel_etat = not bool(publicite.get("actif"))

        if nouvel_etat:
            emplacement = publicite.get("emplacement")
            autre_pub = supabase.table("publicites").select("id").eq("emplacement", emplacement).eq("actif", True).neq("id", pub_id).limit(1).execute()
            if autre_pub.data:
                return "Impossible d'activer cette publicité : l'emplacement est déjà occupé.", 409

        supabase.table("publicites").update({"actif": nouvel_etat}).eq("id", pub_id).execute()
    except Exception as e:
        print("ERREUR ACTIVATION PUBLICITE :", str(e))
        return "Erreur lors de la modification de la publicité.", 500

    return redirect(url_for("ads"))


@app.route("/ads/supprimer/<int:pub_id>", methods=["POST"])
@ads_required
def ads_supprimer(pub_id):
    try:
        supabase.table("publicites").delete().eq("id", pub_id).execute()
    except Exception as e:
        print("ERREUR SUPPRESSION PUBLICITE :", str(e))
        return "Erreur lors de la suppression.", 500

    return redirect(url_for("ads"))


@app.route("/api/ads/impression/<int:pub_id>", methods=["POST"])
def ads_impression(pub_id):
    try:
        resultat = supabase.table("publicites").select("impressions, actif").eq("id", pub_id).limit(1).execute()
        publicites = resultat.data or []
        if not publicites:
            return {"success": False}, 404

        publicite = publicites[0]
        if not publicite.get("actif"):
            return {"success": False}

        impressions = publicite.get("impressions") or 0
        supabase.table("publicites").update({"impressions": impressions + 1}).eq("id", pub_id).execute()
        return {"success": True}
    except Exception as e:
        print("ERREUR IMPRESSION PUBLICITE :", str(e))
        return {"success": False}, 500


@app.route("/ads/clic/<int:pub_id>", methods=["GET"])
def ads_clic(pub_id):
    try:
        resultat = supabase.table("publicites").select("clics, actif, lien").eq("id", pub_id).limit(1).execute()
        publicites = resultat.data or []
        if not publicites:
            abort(404)

        publicite = publicites[0]
        if not publicite.get("actif"):
            abort(404)

        lien = (publicite.get("lien") or "").strip()
        if not lien:
            return redirect(url_for("accueil"))

        clics = publicite.get("clics") or 0
        supabase.table("publicites").update({"clics": clics + 1}).eq("id", pub_id).execute()
        return redirect(lien)
    except Exception as e:
        print("ERREUR CLIC PUBLICITE :", str(e))
        return redirect(url_for("accueil"))


# ============================================================
# NOVAGAMING AUTOPILOT - ROUTES ADMIN
# ============================================================
@app.route("/admin/ai", methods=["GET"])
@admin_required
def admin_ai():
    try:
        from autopilot import init_autopilot_db, get_autopilot_status
        init_autopilot_db()
        status = get_autopilot_status()
        return render_template(
            "admin_ai.html",
            autopilot_status=status.get("autopilot_status", "inactive"),
            games_today=status.get("games_today", 0),
            daily_limit=status.get("daily_limit", 2),
            partners=status.get("partners", []),
            last_run=status.get("last_run", ""),
            next_run=status.get("next_run", ""),
            logs=status.get("logs", []),
            stats=status.get("stats", {}),
            message=None,
            message_type=None
        )
    except Exception as e:
        return f"<h2>Erreur AutoPilot</h2><pre>{str(e)}</pre>", 500


@app.route("/admin/autopilot/run", methods=["POST"])
@admin_required
def autopilot_run():
    try:
        from autopilot import run_daily_autopilot
        result = run_daily_autopilot()
        message = result.get("message", "Analyse AutoPilot terminée.")
        if result.get("success"):
            flash(message, "success")
        else:
            flash(message, "error")
        return redirect(url_for("admin_ai"))
    except Exception as e:
        flash(f"Erreur AutoPilot : {str(e)}", "error")
        return redirect(url_for("admin_ai"))


@app.route("/admin/autopilot/run/force", methods=["POST"])
@admin_required
def autopilot_force_run():
    try:
        from autopilot import run_daily_autopilot
        result = run_daily_autopilot(force=True)
        message = result.get("message", "Analyse forcée terminée.")
        if result.get("success"):
            flash(message, "success")
        else:
            flash(message, "error")
        return redirect(url_for("admin_ai"))
    except Exception as e:
        flash(f"Erreur AutoPilot forcé : {str(e)}", "error")
        return redirect(url_for("admin_ai"))


# =========================================================================
# ROUTE D'AUTO-PUBLICATION IA VERS VOTRE TABLE 'jeux' (Code: 3004)
# =========================================================================
@app.route('/api/admin/games', methods=['POST'])
@app.route('/admin/api/games', methods=['POST'])
@app.route('/admin/publish', methods=['POST'])
def publish_game_to_supabase():
    try:
        # 1. Vérification sécurisée du code d'accès administrateur (3004)
        auth_header = request.headers.get('Authorization', '')
        custom_header = request.headers.get('X-Admin-Code', '')
        data = request.get_json(silent=True) or {}

        provided_code = (
            custom_header 
            or data.get('accessCode') 
            or data.get('authCode')
            or auth_header.replace('Bearer ', '').strip()
        )

        if str(provided_code) != CODE_ADMIN:
            return jsonify({
                "success": False, 
                "error": "Accès refusé : Code administrateur 3004 invalide."
            }), 403

        # Si le jeu est encapsulé dans data.get('game') ou à la racine
        game_data = data.get('game') if isinstance(data.get('game'), dict) else data

        nom_jeu = game_data.get('title') or game_data.get('nom')
        if not nom_jeu:
            return jsonify({"success": False, "error": "Le nom du jeu est obligatoire."}), 400

        slug = re.sub(r'[^a-zA-Z0-9]+', '-', nom_jeu.lower()).strip('-')

        # 2. Gestion de la jaquette principale (couverture) via Cloudinary
        raw_couverture = game_data.get('coverImage') or game_data.get('couverture') or ''
        couverture_url = raw_couverture
        if raw_couverture and raw_couverture.startswith('http'):
            try:
                res_cover = cloudinary.uploader.upload(
                    raw_couverture,
                    folder="novagaming/couvertures",
                    public_id=f"cover_{slug}"
                )
                couverture_url = res_cover.get('secure_url', raw_couverture)
            except Exception as e:
                print(f"[Cloudinary Warning] Erreur upload couverture: {e}")

        # 3. Gestion des captures d'écran (image1 ... image10) via Cloudinary
        screenshots = game_data.get('screenshots') or []
        images_dict = {}
        for idx in range(1, 11):
            col_name = f"image{idx}"
            img_src = game_data.get(col_name)
            
            # Si non spécifié individuellement, on pioche dans la liste screenshots
            if not img_src and len(screenshots) >= idx:
                img_src = screenshots[idx - 1]

            if img_src and str(img_src).startswith('http'):
                try:
                    res_img = cloudinary.uploader.upload(
                        img_src,
                        folder="novagaming/screenshots",
                        public_id=f"{slug}_screenshot_{idx}"
                    )
                    images_dict[col_name] = res_img.get('secure_url', img_src)
                except Exception as e:
                    print(f"[Cloudinary Warning] Erreur upload {col_name}: {e}")
                    images_dict[col_name] = img_src
            else:
                images_dict[col_name] = img_src or ""

        # 4. Traitement des liens de téléchargement
        download_links = game_data.get('downloadLinks') or []
        if isinstance(download_links, list) and len(download_links) > 0:
            premier_lien = download_links[0].get('url') if isinstance(download_links[0], dict) else str(download_links[0])
            lien_principal = premier_lien
        else:
            lien_principal = game_data.get('lien') or ''

        # 5. Préparation de la ligne pour votre table Supabase 'jeux'
        jeu_payload = {
            "nom": nom_jeu,
            "console": game_data.get('platform') or game_data.get('console') or 'PC Windows',
            "description": game_data.get('description') or game_data.get('shortDescription') or '',
            "taille": game_data.get('fileSize') or game_data.get('taille') or 'Inconnue',
            "version": game_data.get('version') or '1.0',
            "langue": game_data.get('langue') or 'Français / Multi',
            "couverture": couverture_url,
            "lien": lien_principal,
            "telechargements": 0,
            **images_dict  # Remplit automatiquement image1, image2, ..., image10
        }

        # 6. Insertion directe dans Supabase (table 'jeux')
        supabase_response = supabase.table('jeux').insert(jeu_payload).execute()

        print(f"✅ [NovaGaming] Jeu ajouté avec succès dans la table 'jeux' : {nom_jeu}")

        # Notification dans Supabase
        try:
            supabase.table("notifications").insert({
                "titre": "Nouveau jeu publié ⚡",
                "message": f"{nom_jeu} a été publié automatiquement.",
                "lu": 0
            }).execute()
        except Exception:
            pass

        return jsonify({
            "success": True,
            "message": f"Le jeu '{nom_jeu}' a été enregistré et publié avec succès dans la table 'jeux' !",
            "data": supabase_response.data
        }), 201

    except Exception as err:
        print(f"❌ [NovaGaming Error] : {err}")
        return jsonify({"success": False, "error": str(err)}), 500


# ==========================
# LANCEMENT DU SERVEUR
# ==========================
if __name__ == "__main__":
    print("")
    print("==============================")
    print("🎮 GAME STORE (NOVAGAMING)")
    print("==============================")
    print("☁️ Base de données : Supabase")
    print("📸 Images : Cloudinary")
    print("🔐 Administration : /login")
    print("🏠 Accueil : /")
    print("==============================")
    print("🚀 Serveur démarré sur http://localhost:5000")
    print("==============================")
    print("")

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=True
    )
