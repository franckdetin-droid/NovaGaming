# app.py - PARTIE 1/4
# ==========================

import os

import cloudinary
import cloudinary.uploader

from supabase import create_client, Client

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

from functools import wraps


# ==========================
# CONFIGURATION FLASK
# ==========================

app = Flask(__name__)

app.secret_key = "CHANGE-MOI-PAR-UNE-CLE-SECRETE"

CODE_ADMIN = "3004"


# ==========================
# SUPABASE
# ==========================

SUPABASE_URL = "https://uavklduzgwzdwzngtpgg.supabase.co"

# Mets ici ta clé anon / publishable Supabase
SUPABASE_KEY = "sb_publishable_8FNC-V2NgSlOLEuxEx2N4Q_tcaTxaqv"

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


# ==========================
# CLOUDINARY
# ==========================

cloudinary.config(
    cloud_name="zgp2vxel",
    api_key="357264626165689",
    api_secret="CkGRcrzSyk4gR-PIA3WC5jMItFI"
)


# ==========================
# FONCTIONS SUPABASE
# ==========================

def get_jeux():
    resultat = (
        supabase
        .table("jeux")
        .select("*")
        .order("id", desc=True)
        .execute()
    )

    return resultat.data or []


def get_jeu(jeu_id):

    resultat = (
        supabase
        .table("jeux")
        .select("*")
        .eq("id", jeu_id)
        .limit(1)
        .execute()
    )

    if not resultat.data:
        return None

    return resultat.data[0]


# ==========================
# UPLOAD IMAGE CLOUDINARY
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

        image_url = resultat.get("secure_url")

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

    jeux = get_jeux()

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

    if q:

        resultat = (
            supabase
            .table("jeux")
            .select("*")
            .or_(
                f"nom.ilike.%{q}%,"
                f"console.ilike.%{q}%,"
                f"description.ilike.%{q}%"
            )
            .order("id", desc=True)
            .execute()
        )

        jeux = resultat.data or []

    else:

        jeux = get_jeux()

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

    jeu_data = get_jeu(jeu_id)

    if not jeu_data:
        abort(404)

    commentaires_resultat = (
        supabase
        .table("commentaires")
        .select("*")
        .eq("jeu_id", jeu_id)
        .order("id", desc=True)
        .execute()
    )

    commentaires = commentaires_resultat.data or []

    return render_template(
        "jeu.html",
        jeu=jeu_data,
        commentaires=commentaires
    )


# ==========================
# TELECHARGEMENT
# ==========================

@app.route("/telecharger/<int:jeu_id>")
def telecharger(jeu_id):

    jeu_data = get_jeu(jeu_id)

    if not jeu_data:
        abort(404)

    lien = jeu_data.get("lien")

    if not lien:

        return (
            "Lien de téléchargement indisponible.",
            404
        )

    ancien_nombre = (
        jeu_data.get("telechargements")
        or 0
    )

    (
        supabase
        .table("jeux")
        .update({
            "telechargements":
                ancien_nombre + 1
        })
        .eq("id", jeu_id)
        .execute()
    )

    return redirect(lien)


# ==========================
# COMMENTAIRE
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

    jeu_existe = get_jeu(jeu_id)

    if jeu_existe:

        (
            supabase
            .table("commentaires")
            .insert({
                "jeu_id": jeu_id,
                "pseudo": pseudo,
                "commentaire": texte
            })
            .execute()
        )

        (
            supabase
            .table("notifications")
            .insert({
                "titre": "Nouveau commentaire 💬",
                "message":
                    f"{pseudo} a commenté un jeu.",
                "lu": 0
            })
            .execute()
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
        # app.py - PARTIE 2/4
# ==========================


# ==========================
# ADMINISTRATION
# ==========================

@app.route("/admin")
@admin_required
def admin():

    jeux = get_jeux()

    total_jeux = len(jeux)

    total_telechargements = sum(
        (jeu.get("telechargements") or 0)
        for jeu in jeux
    )

    commentaires_resultat = (
        supabase
        .table("commentaires")
        .select("*")
        .order("id", desc=True)
        .limit(30)
        .execute()
    )

    commentaires_admin = (
        commentaires_resultat.data or []
    )

    total_commentaires_resultat = (
        supabase
        .table("commentaires")
        .select("id", count="exact")
        .execute()
    )

    total_commentaires = (
        total_commentaires_resultat.count or 0
    )

    notifications_resultat = (
        supabase
        .table("notifications")
        .select("*")
        .order("id", desc=True)
        .limit(10)
        .execute()
    )

    notifications_admin = (
        notifications_resultat.data or []
    )

    return render_template(
        "admin.html",
        jeux=jeux,
        total_jeux=total_jeux,
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
            couverture = image_couverture


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
            images.append(image_url)

    while len(images) < 10:
        images.append("")


    # ==========================
    # INSERTION SUPABASE
    # ==========================

    donnees = {
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
        "telechargements": 0
    }

    (
        supabase
        .table("jeux")
        .insert(donnees)
        .execute()
    )


    # ==========================
    # NOTIFICATION
    # ==========================

    (
        supabase
        .table("notifications")
        .insert({
            "titre":
                "Nouveau jeu disponible 🎮",
            "message":
                f"{nom} vient d'être ajouté "
                "au catalogue.",
            "lu": 0
        })
        .execute()
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

    jeu_data = get_jeu(jeu_id)

    if not jeu_data:
        abort(404)


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
            couverture = nouvelle_couverture

    elif not couverture:

        couverture = (
            jeu_data.get("couverture")
            or ""
        )


    # ==========================
    # ANCIENNES IMAGES
    # ==========================

    anciennes_images = []

    for numero in range(1, 11):

        anciennes_images.append(
            jeu_data.get(
                f"image{numero}"
            ) or ""
        )


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


    if nouvelles_images:

        images = nouvelles_images

        while len(images) < 10:
            images.append("")

    else:

        images = anciennes_images


    # ==========================
    # UPDATE SUPABASE
    # ==========================

    donnees = {
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
    }

    (
        supabase
        .table("jeux")
        .update(donnees)
        .eq("id", jeu_id)
        .execute()
    )


    # ==========================
    # NOTIFICATION
    # ==========================

    (
        supabase
        .table("notifications")
        .insert({
            "titre": "Jeu modifié ✏️",
            "message":
                f"{nom} a été modifié.",
            "lu": 0
        })
        .execute()
    )

    return redirect(
        url_for("admin")
        )
    # app.py - PARTIE 3/4
# ==========================


# ==========================
# SUPPRIMER UN JEU
# ==========================

@app.route(
    "/admin/supprimer/<int:jeu_id>"
)
@admin_required
def supprimer(jeu_id):

    jeu_data = get_jeu(jeu_id)

    if not jeu_data:
        abort(404)


    # ==========================
    # SUPPRIMER COMMENTAIRES
    # ==========================

    (
        supabase
        .table("commentaires")
        .delete()
        .eq("jeu_id", jeu_id)
        .execute()
    )


    # ==========================
    # SUPPRIMER FAVORIS
    # ==========================

    (
        supabase
        .table("favoris")
        .delete()
        .eq("jeu_id", jeu_id)
        .execute()
    )


    # ==========================
    # SUPPRIMER VUES
    # ==========================

    (
        supabase
        .table("vues")
        .delete()
        .eq("jeu_id", jeu_id)
        .execute()
    )


    # ==========================
    # SUPPRIMER LE JEU
    # ==========================

    (
        supabase
        .table("jeux")
        .delete()
        .eq("id", jeu_id)
        .execute()
    )


    # ==========================
    # NOTIFICATION
    # ==========================

    (
        supabase
        .table("notifications")
        .insert({
            "titre":
                "Jeu supprimé 🗑️",
            "message":
                f"{jeu_data.get('nom', 'Jeu')} "
                "a été supprimé du catalogue.",
            "lu": 0
        })
        .execute()
    )

    return redirect(
        url_for("admin")
    )


# ==========================
# SUPPRIMER COMMENTAIRE
# ==========================

@app.route(
    "/admin/commentaire/supprimer/"
    "<int:commentaire_id>"
)
@admin_required
def supprimer_commentaire(
    commentaire_id
):

    (
        supabase
        .table("commentaires")
        .delete()
        .eq("id", commentaire_id)
        .execute()
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

    ip = request.remote_addr

    jeu_data = get_jeu(jeu_id)

    if not jeu_data:
        abort(404)


    resultat = (
        supabase
        .table("favoris")
        .select("id")
        .eq("jeu_id", jeu_id)
        .eq("ip", ip)
        .limit(1)
        .execute()
    )

    existe = resultat.data or []


    if existe:

        (
            supabase
            .table("favoris")
            .delete()
            .eq("jeu_id", jeu_id)
            .eq("ip", ip)
            .execute()
        )

    else:

        (
            supabase
            .table("favoris")
            .insert({
                "jeu_id": jeu_id,
                "ip": ip
            })
            .execute()
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

@app.route("/notifications")
def notifications():

    resultat = (
        supabase
        .table("notifications")
        .select("*")
        .order("id", desc=True)
        .execute()
    )

    liste = resultat.data or []

    return render_template(
        "notifications.html",
        notifications=liste
    )


# ==========================
# MARQUER NOTIFICATIONS
# ==========================

@app.route(
    "/notifications/lues",
    methods=["POST"]
)
def notifications_lues():

    (
        supabase
        .table("notifications")
        .update({
            "lu": 1
        })
        .eq("lu", 0)
        .execute()
    )

    return redirect(
        url_for("notifications")
    )


# ==========================
# JEUX POPULAIRES
# ==========================

@app.route("/populaires")
def populaires():

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

    return render_template(
        "index.html",
        jeux=jeux,
        titre="🔥 Jeux populaires"
    )


# ==========================
# NOUVEAUTES
# ==========================

@app.route("/nouveautes")
def nouveautes():

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


    # ==========================
    # VUE RECENTE
    # ==========================

    resultat = (
        supabase
        .table("vues")
        .select("id")
        .eq("jeu_id", jeu_id)
        .eq("ip", ip)
        .gte(
            "date",
            "now() - interval '30 minutes'"
        )
        .limit(1)
        .execute()
    )

    # Si Supabase ne retourne rien,
    # enregistrer la vue.

    if not resultat.data:

        (
            supabase
            .table("vues")
            .insert({
                "jeu_id": jeu_id,
                "ip": ip
            })
            .execute()
        )


# ==========================
# FONCTIONS GLOBALES
# ==========================

@app.context_processor
def fonctions_globales():

    def nombre_favoris(jeu_id):

        resultat = (
            supabase
            .table("favoris")
            .select(
                "id",
                count="exact"
            )
            .eq("jeu_id", jeu_id)
            .execute()
        )

        return resultat.count or 0

    return {
        "nombre_favoris":
            nombre_favoris
    }


# ==========================
# STATISTIQUES GLOBALES
# ==========================

@app.context_processor
def statistiques_globales():

    jeux_resultat = (
        supabase
        .table("jeux")
        .select(
            "id,telechargements"
        )
        .execute()
    )

    jeux = jeux_resultat.data or []


    total_jeux = len(jeux)

    total_telechargements = sum(
        (jeu.get("telechargements") or 0)
        for jeu in jeux
    )


    commentaires_resultat = (
        supabase
        .table("commentaires")
        .select(
            "id",
            count="exact"
        )
        .execute()
    )

    total_commentaires = (
        commentaires_resultat.count or 0
    )


    notifications_resultat = (
        supabase
        .table("notifications")
        .select(
            "id",
            count="exact"
        )
        .eq("lu", 0)
        .execute()
    )

    notifications_non_lues = (
        notifications_resultat.count or 0
    )


    return {

        "total_commentaires":
            total_commentaires,

        "total_jeux":
            total_jeux,

        "total_telechargements":
            total_telechargements,

        "notifications_non_lues":
            notifications_non_lues
    }
)
# app.py - PARTIE 4/4
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

        <meta name="viewport"
              content="width=device-width,
              initial-scale=1.0">

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

    print(
        "ERREUR 500 :",
        error
    )

    return """
    <!DOCTYPE html>
    <html lang="fr">

    <head>

        <meta charset="UTF-8">

        <meta name="viewport"
              content="width=device-width,
              initial-scale=1.0">

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
# LANCEMENT
# ==========================

if __name__ == "__main__":

    print("")
    print("==============================")
    print("🎮 NOVAGAMING")
    print("==============================")
    print("")
    print("☁️ Base de données :")
    print("Supabase")
    print("")
    print("🖼️ Images :")
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
