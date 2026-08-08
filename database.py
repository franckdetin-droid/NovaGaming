# database.py

import sqlite3


# ==========================
# CONFIGURATION
# ==========================

DB_NAME = "jeux.db"


# ==========================
# CONNEXION
# ==========================

def connexion():

    conn = sqlite3.connect(DB_NAME)

    conn.row_factory = sqlite3.Row

    return conn


# ==========================
# CREATION DE LA BASE
# ==========================

def creer_base():

    conn = connexion()

    cur = conn.cursor()


    # ==========================
    # TABLE JEUX
    # ==========================

    cur.execute("""
    CREATE TABLE IF NOT EXISTS jeux(

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        nom TEXT NOT NULL,

        console TEXT,

        description TEXT,

        taille TEXT,

        version TEXT,

        langue TEXT,

        couverture TEXT,

        image1 TEXT,
        image2 TEXT,
        image3 TEXT,
        image4 TEXT,
        image5 TEXT,
        image6 TEXT,
        image7 TEXT,
        image8 TEXT,
        image9 TEXT,
        image10 TEXT,

        lien TEXT,

        telechargements INTEGER DEFAULT 0,

        date_ajout
            TIMESTAMP DEFAULT CURRENT_TIMESTAMP

    )
    """)


    # ==========================
    # TABLE COMMENTAIRES
    # ==========================

    cur.execute("""
    CREATE TABLE IF NOT EXISTS commentaires(

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        jeu_id INTEGER NOT NULL,

        pseudo TEXT,

        commentaire TEXT NOT NULL,

        date_commentaire
            TIMESTAMP DEFAULT CURRENT_TIMESTAMP

    )
    """)


    # ==========================
    # TABLE FAVORIS
    # ==========================

    cur.execute("""
    CREATE TABLE IF NOT EXISTS favoris(

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        jeu_id INTEGER NOT NULL,

        ip TEXT NOT NULL

    )
    """)


    # ==========================
    # TABLE VUES
    # ==========================

    cur.execute("""
    CREATE TABLE IF NOT EXISTS vues(

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        jeu_id INTEGER NOT NULL,

        ip TEXT,

        date
            TIMESTAMP DEFAULT CURRENT_TIMESTAMP

    )
    """)


    # ==========================
    # TABLE NOTIFICATIONS
    # ==========================

    cur.execute("""
    CREATE TABLE IF NOT EXISTS notifications(

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        titre TEXT NOT NULL,

        message TEXT NOT NULL,

        lu INTEGER DEFAULT 0,

        date
            TIMESTAMP DEFAULT CURRENT_TIMESTAMP

    )
    """)


    # ==========================
    # TABLE PARAMETRES
    # ==========================

    cur.execute("""
    CREATE TABLE IF NOT EXISTS parametres(

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        nom_site TEXT,

        logo TEXT,

        footer TEXT,

        email_admin TEXT

    )
    """)


    # ==========================
    # PARAMETRES PAR DEFAUT
    # ==========================

    cur.execute("""
        SELECT COUNT(*)
        FROM parametres
    """)

    nombre = cur.fetchone()[0]


    if nombre == 0:

        cur.execute("""
        INSERT INTO parametres(

            nom_site,

            logo,

            footer,

            email_admin

        )

        VALUES(

            ?,
            ?,
            ?,
            ?

        )
        """, (

            "Game Store",

            "",

            "Fait par Franck",

            "dtech4319@gmail.com"

        ))


    # ==========================
    # INDEX
    # ==========================

    cur.execute("""
        CREATE INDEX IF NOT EXISTS
        index_jeux_nom
        ON jeux(nom)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS
        index_commentaires_jeu
        ON commentaires(jeu_id)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS
        index_favoris_jeu
        ON favoris(jeu_id)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS
        index_vues_jeu
        ON vues(jeu_id)
    """)


    # ==========================
    # SAUVEGARDE
    # ==========================

    conn.commit()

    conn.close()


# ==========================
# CREATION AUTOMATIQUE
# ==========================

if __name__ == "__main__":

    creer_base()

    print(
        "✅ Base de données créée avec succès."
    )