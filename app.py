# app.py - PARTIE 1/4
# ==========================

import os
import sqlite3

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    abort
)

from functools import wraps

from database import (
    connexion,
    creer_base
)


# ==========================
# CONFIGURATION
# ==========================

app = Flask(__name__)

app.secret_key = "CHANGE-MOI-PAR-UNE-CLE-SECRETE"

CODE_ADMIN = "3004"


# ==========================
# DOSSIERS IMAGES
# ==========================

DOSSIER_UPLOADS = os.path.join(
    app.static_folder,
    "uploads",
    "jeux"
)

os.makedirs(
    DOSSIER_UPLOADS,
    exist_ok=True
)


# ==========================
# INITIALISATION
# ==========================

creer_base()


# ==========================
# CREATION DES TABLES
# SUPPLEMENTAIRES
# ==========================

def creer_tables_supplementaires():

    conn = connexion()

    # Favoris
    conn.execute("""
        CREATE TABLE IF NOT EXISTS favoris(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            jeu_id INTEGER NOT NULL,
            ip TEXT NOT NULL
        )
    """)

    # Vues
    conn.execute("""
        CREATE TABLE IF NOT EXISTS vues(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            jeu_id INTEGER NOT NULL,
            ip TEXT,
            date TIMESTAMP
                DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Notifications
    conn.execute("""
        CREATE TABLE IF NOT EXISTS notifications(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titre TEXT NOT NULL,
            message TEXT NOT NULL,
            lu INTEGER DEFAULT 0,
            date TIMESTAMP
                DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Vérification de la colonne "lu"
    colonnes = [
        ligne[1]
        for ligne in conn.execute(
            "PRAGMA table_info(notifications)"
        ).fetchall()
    ]

    if "lu" not in colonnes:

        conn.execute("""
            ALTER TABLE notifications
            ADD COLUMN lu INTEGER DEFAULT 0
        """)

    conn.commit()
    conn.close()


creer_tables_supplementaires()


# ==========================
# FONCTION UPLOAD IMAGE
# ==========================

def enregistrer_image(fichier, nom_base):

    if not fichier:
        return None

    if not fichier.filename:
        return None

    # Vérification simple du type
    if not fichier.mimetype.startswith("image/"):
        return None

    extension = os.path.splitext(
        fichier.filename
    )[1].lower()

    extensions_autorisees = {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".gif"
    }

    if extension not in extensions_autorisees:
        return None

    # Nom sécurisé
    nom_fichier = (
        nom_base
        + "_"
        + str(os.getpid())
        + "_"
        + str(abs(hash(fichier.filename)))
        + extension
    )

    chemin = os.path.join(
        DOSSIER_UPLOADS,
        nom_fichier
    )

    fichier.save(chemin)

    # Chemin utilisable par Flask
    return url_for(
        "static",
        filename="uploads/jeux/" + nom_fichier
    )


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

    conn = connexion()

    jeux = conn.execute("""
        SELECT *
        FROM jeux
        ORDER BY id DESC
    """).fetchall()

    conn.close()

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

    conn = connexion()

    if q:

        jeux = conn.execute("""
            SELECT *
            FROM jeux
            WHERE nom LIKE ?
               OR console LIKE ?
               OR description LIKE ?
            ORDER BY id DESC
        """, (
            f"%{q}%",
            f"%{q}%",
            f"%{q}%"
        )).fetchall()

    else:

        jeux = conn.execute("""
            SELECT *
            FROM jeux
            ORDER BY id DESC
        """).fetchall()

    conn.close()

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

    conn = connexion()

    jeu = conn.execute("""
        SELECT *
        FROM jeux
        WHERE id=?
    """, (
        jeu_id,
    )).fetchone()

    if not jeu:

        conn.close()

        abort(404)

    commentaires = conn.execute("""
        SELECT *
        FROM commentaires
        WHERE jeu_id=?
        ORDER BY id DESC
    """, (
        jeu_id,
    )).fetchall()

    conn.close()

    return render_template(
        "jeu.html",
        jeu=jeu,
        commentaires=commentaires
    )


# ==========================
# TELECHARGEMENT
# ==========================

@app.route(
    "/telecharger/<int:jeu_id>"
)
def telecharger(jeu_id):

    conn = connexion()

    jeu = conn.execute("""
        SELECT *
        FROM jeux
        WHERE id=?
    """, (
        jeu_id,
    )).fetchone()

    if not jeu:

        conn.close()

        abort(404)

    lien = jeu["lien"]

    if not lien:

        conn.close()

        return (
            "Lien de téléchargement indisponible.",
            404
        )

    conn.execute("""
        UPDATE jeux
        SET telechargements =
            telechargements + 1
        WHERE id=?
    """, (
        jeu_id,
    ))

    conn.commit()
    conn.close()

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

    conn = connexion()

    jeu_existe = conn.execute("""
        SELECT id
        FROM jeux
        WHERE id=?
    """, (
        jeu_id,
    )).fetchone()

    if jeu_existe:

        conn.execute("""
            INSERT INTO commentaires(
                jeu_id,
                pseudo,
                commentaire
            )
            VALUES(?, ?, ?)
        """, (
            jeu_id,
            pseudo,
            texte
        ))

        conn.execute("""
            INSERT INTO notifications(
                titre,
                message,
                lu
            )
            VALUES(?, ?, 0)
        """, (
            "Nouveau commentaire 💬",
            f"{pseudo} a commenté un jeu."
        ))

        conn.commit()

    conn.close()

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
    # app.py - PARTIE 2/4
# ==========================


# ==========================
# ADMINISTRATION
# ==========================

@app.route("/admin")
@admin_required
def admin():

    conn = connexion()

    jeux = conn.execute("""
        SELECT *
        FROM jeux
        ORDER BY id DESC
    """).fetchall()

    total_jeux = conn.execute("""
        SELECT COUNT(*)
        FROM jeux
    """).fetchone()[0]

    total_telechargements = conn.execute("""
        SELECT COALESCE(
            SUM(telechargements),
            0
        )
        FROM jeux
    """).fetchone()[0]

    total_commentaires = conn.execute("""
        SELECT COUNT(*)
        FROM commentaires
    """).fetchone()[0]

    # Derniers commentaires
    commentaires_admin = conn.execute("""
        SELECT *
        FROM commentaires
        ORDER BY id DESC
        LIMIT 30
    """).fetchall()

    # Dernières notifications
    notifications_admin = conn.execute("""
        SELECT *
        FROM notifications
        ORDER BY id DESC
        LIMIT 10
    """).fetchall()

    conn.close()

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

    if couverture_file and couverture_file.filename:

        image_couverture = enregistrer_image(
            couverture_file,
            "couverture"
        )

        if image_couverture:

            couverture = image_couverture


    # ==========================
    # GALERIE
    # ==========================

    fichiers_images = request.files.getlist(
        "images"
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
    # INSERTION SQLITE
    # ==========================

    conn = connexion()

    curseur = conn.execute("""
        INSERT INTO jeux(
            nom,
            console,
            description,
            taille,
            version,
            langue,
            couverture,
            image1,
            image2,
            image3,
            image4,
            image5,
            image6,
            image7,
            image8,
            image9,
            image10,
            lien
        )
        VALUES(
            ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
    """, (
        nom,
        console,
        description,
        taille,
        version,
        langue,
        couverture,
        image1,
        image2,
        image3,
        image4,
        image5,
        image6,
        image7,
        image8,
        image9,
        image10,
        lien
    ))

    jeu_id = curseur.lastrowid


    # ==========================
    # NOTIFICATION
    # ==========================

    conn.execute("""
        INSERT INTO notifications(
            titre,
            message,
            lu
        )
        VALUES(?, ?, 0)
    """, (
        "Nouveau jeu disponible 🎮",
        f"{nom} vient d'être ajouté au catalogue."
    ))


    conn.commit()
    conn.close()


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

    conn = connexion()

    jeu = conn.execute("""
        SELECT *
        FROM jeux
        WHERE id=?
    """, (
        jeu_id,
    )).fetchone()

    if not jeu:

        conn.close()

        abort(404)


    # ==========================
    # AFFICHAGE
    # ==========================

    if request.method == "GET":

        conn.close()

        return render_template(
            "modifier.html",
            jeu=jeu
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

        conn.close()

        return (
            "Le nom du jeu est obligatoire.",
            400
        )

    if not lien:

        conn.close()

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

    if couverture_file and couverture_file.filename:

        nouvelle_couverture = enregistrer_image(
            couverture_file,
            "couverture"
        )

        if nouvelle_couverture:

            couverture = nouvelle_couverture

    else:

        # Garder l'ancienne image
        if not couverture:

            couverture = jeu["couverture"] or ""


    # ==========================
    # GALERIE
    # ==========================

    fichiers_images = request.files.getlist(
        "images"
    )


    anciennes_images = [
        jeu["image1"] or "",
        jeu["image2"] or "",
        jeu["image3"] or "",
        jeu["image4"] or "",
        jeu["image5"] or "",
        jeu["image6"] or "",
        jeu["image7"] or "",
        jeu["image8"] or "",
        jeu["image9"] or "",
        jeu["image10"] or ""
    ]


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


    # Si aucune nouvelle image n'est envoyée,
    # on conserve les anciennes.

    if nouvelles_images:

        images = nouvelles_images

        while len(images) < 10:

            images.append("")

    else:

        images = anciennes_images


    # ==========================
    # UPDATE
    # ==========================

    conn.execute("""
        UPDATE jeux
        SET
            nom=?,
            console=?,
            description=?,
            taille=?,
            version=?,
            langue=?,
            couverture=?,
            image1=?,
            image2=?,
            image3=?,
            image4=?,
            image5=?,
            image6=?,
            image7=?,
            image8=?,
            image9=?,
            image10=?,
            lien=?
        WHERE id=?
    """, (
        nom,
        console,
        description,
        taille,
        version,
        langue,
        couverture,
        images[0],
        images[1],
        images[2],
        images[3],
        images[4],
        images[5],
        images[6],
        images[7],
        images[8],
        images[9],
        lien,
        jeu_id
    ))


    # ==========================
    # NOTIFICATION
    # ==========================

    conn.execute("""
        INSERT INTO notifications(
            titre,
            message,
            lu
        )
        VALUES(?, ?, 0)
    """, (
        "Jeu modifié ✏️",
        f"{nom} a été modifié."
    ))


    conn.commit()
    conn.close()


    return redirect(
        url_for("admin")
    )


# ==========================
# SUPPRIMER UN JEU
# ==========================

@app.route(
    "/admin/supprimer/<int:jeu_id>"
)
@admin_required
def supprimer(jeu_id):

    conn = connexion()

    jeu = conn.execute("""
        SELECT *
        FROM jeux
        WHERE id=?
    """, (
        jeu_id,
    )).fetchone()

    if not jeu:

        conn.close()

        abort(404)


    # ==========================
    # SUPPRIMER LES DONNEES
    # ==========================

    conn.execute("""
        DELETE FROM commentaires
        WHERE jeu_id=?
    """, (
        jeu_id,
    ))

    conn.execute("""
        DELETE FROM favoris
        WHERE jeu_id=?
    """, (
        jeu_id,
    ))

    conn.execute("""
        DELETE FROM vues
        WHERE jeu_id=?
    """, (
        jeu_id,
    ))

    conn.execute("""
        DELETE FROM jeux
        WHERE id=?
    """, (
        jeu_id,
    ))


    # ==========================
    # NOTIFICATION
    # ==========================

    conn.execute("""
        INSERT INTO notifications(
            titre,
            message,
            lu
        )
        VALUES(?, ?, 0)
    """, (
        "Jeu supprimé 🗑️",
        f"{jeu['nom']} a été supprimé du catalogue."
    ))


    conn.commit()
    conn.close()


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

    conn = connexion()

    conn.execute("""
        DELETE FROM commentaires
        WHERE id=?
    """, (
        commentaire_id,
    ))

    conn.commit()
    conn.close()

    return redirect(
        url_for("admin")
    )
    # app.py - PARTIE 3/4
# ==========================


# ==========================
# FAVORIS
# ==========================

@app.route("/favori/<int:jeu_id>")
def favori(jeu_id):

    ip = request.remote_addr

    conn = connexion()

    jeu = conn.execute("""
        SELECT id
        FROM jeux
        WHERE id=?
    """, (
        jeu_id,
    )).fetchone()

    if not jeu:

        conn.close()

        abort(404)

    existe = conn.execute("""
        SELECT id
        FROM favoris
        WHERE jeu_id=?
        AND ip=?
    """, (
        jeu_id,
        ip
    )).fetchone()

    if existe:

        conn.execute("""
            DELETE FROM favoris
            WHERE jeu_id=?
            AND ip=?
        """, (
            jeu_id,
            ip
        ))

    else:

        conn.execute("""
            INSERT INTO favoris(
                jeu_id,
                ip
            )
            VALUES(?, ?)
        """, (
            jeu_id,
            ip
        ))

    conn.commit()
    conn.close()

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

    conn = connexion()

    liste = conn.execute("""
        SELECT *
        FROM notifications
        ORDER BY id DESC
    """).fetchall()

    conn.close()

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

    conn = connexion()

    # Vérifier que la colonne existe
    colonnes = [
        ligne[1]
        for ligne in conn.execute(
            "PRAGMA table_info(notifications)"
        ).fetchall()
    ]

    if "lu" not in colonnes:

        conn.execute("""
            ALTER TABLE notifications
            ADD COLUMN lu INTEGER DEFAULT 0
        """)

        conn.commit()

    conn.execute("""
        UPDATE notifications
        SET lu=1
        WHERE lu=0
    """)

    conn.commit()
    conn.close()

    return redirect(
        url_for("notifications")
    )


# ==========================
# JEUX POPULAIRES
# ==========================

@app.route("/populaires")
def populaires():

    conn = connexion()

    jeux = conn.execute("""
        SELECT *
        FROM jeux
        ORDER BY telechargements DESC
        LIMIT 20
    """).fetchall()

    conn.close()

    return render_template(
        "index.html",
        jeux=jeux,
        titre="🔥 Jeux populaires"
    )


# ==========================
# NOUVEAUTÉS
# ==========================

@app.route("/nouveautes")
def nouveautes():

    conn = connexion()

    jeux = conn.execute("""
        SELECT *
        FROM jeux
        ORDER BY date_ajout DESC
        LIMIT 20
    """).fetchall()

    conn.close()

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

    # Seulement sur une page de jeu
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

    conn = connexion()

    # Vérifier si cette IP a déjà
    # consulté ce jeu récemment.

    existe = conn.execute("""
        SELECT id
        FROM vues
        WHERE jeu_id=?
        AND ip=?
        AND date > datetime(
            'now',
            '-30 minutes'
        )
        LIMIT 1
    """, (
        jeu_id,
        ip
    )).fetchone()

    if not existe:

        conn.execute("""
            INSERT INTO vues(
                jeu_id,
                ip
            )
            VALUES(?, ?)
        """, (
            jeu_id,
            ip
        ))

        conn.commit()

    conn.close()


# ==========================
# NOMBRE DE FAVORIS
# ==========================

@app.context_processor
def fonctions_globales():

    def nombre_favoris(jeu_id):

        conn = connexion()

        resultat = conn.execute("""
            SELECT COUNT(*)
            FROM favoris
            WHERE jeu_id=?
        """, (
            jeu_id,
        )).fetchone()[0]

        conn.close()

        return resultat

    return {
        "nombre_favoris": nombre_favoris
    }


# ==========================
# STATISTIQUES GLOBALES
# ==========================

@app.context_processor
def statistiques_globales():

    conn = connexion()

    # ==========================
    # COMMENTAIRES
    # ==========================

    commentaires = conn.execute("""
        SELECT COUNT(*)
        FROM commentaires
    """).fetchone()[0]


    # ==========================
    # JEUX
    # ==========================

    jeux = conn.execute("""
        SELECT COUNT(*)
        FROM jeux
    """).fetchone()[0]


    # ==========================
    # TELECHARGEMENTS
    # ==========================

    telechargements = conn.execute("""
        SELECT COALESCE(
            SUM(telechargements),
            0
        )
        FROM jeux
    """).fetchone()[0]


    # ==========================
    # NOTIFICATIONS NON LUES
    # ==========================

    colonnes = [
        ligne[1]
        for ligne in conn.execute(
            "PRAGMA table_info(notifications)"
        ).fetchall()
    ]


    if "lu" in colonnes:

        notifications_non_lues = conn.execute("""
            SELECT COUNT(*)
            FROM notifications
            WHERE lu=0
        """).fetchone()[0]

    else:

        notifications_non_lues = 0


    conn.close()


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
              content="width=device-width, initial-scale=1.0">

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
        <meta name="viewport"
              content="width=device-width, initial-scale=1.0">

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
# VERIFICATION DE LA BASE
# ==========================

def verifier_base():

    conn = connexion()

    # ==========================
    # TABLE NOTIFICATIONS
    # ==========================

    colonnes_notifications = [
        ligne[1]
        for ligne in conn.execute(
            "PRAGMA table_info(notifications)"
        ).fetchall()
    ]

    if "lu" not in colonnes_notifications:

        conn.execute("""
            ALTER TABLE notifications
            ADD COLUMN lu INTEGER DEFAULT 0
        """)


    # ==========================
    # TABLE FAVORIS
    # ==========================

    conn.execute("""
        CREATE TABLE IF NOT EXISTS favoris(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            jeu_id INTEGER NOT NULL,
            ip TEXT NOT NULL
        )
    """)


    # ==========================
    # TABLE VUES
    # ==========================

    conn.execute("""
        CREATE TABLE IF NOT EXISTS vues(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            jeu_id INTEGER NOT NULL,
            ip TEXT,
            date TIMESTAMP
                DEFAULT CURRENT_TIMESTAMP
        )
    """)


    # ==========================
    # TABLE NOTIFICATIONS
    # ==========================

    conn.execute("""
        CREATE TABLE IF NOT EXISTS notifications(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titre TEXT NOT NULL,
            message TEXT NOT NULL,
            lu INTEGER DEFAULT 0,
            date TIMESTAMP
                DEFAULT CURRENT_TIMESTAMP
        )
    """)


    conn.commit()
    conn.close()


# ==========================
# VERIFICATION AU DEMARRAGE
# ==========================

verifier_base()


# ==========================
# LANCEMENT
# ==========================

if __name__ == "__main__":

    print("")
    print("==============================")
    print("🎮 GAME STORE")
    print("==============================")
    print("")
    print("📁 Images :")
    print(DOSSIER_UPLOADS)
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