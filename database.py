# database.py
# ==========================
# CONNEXION SUPABASE
# ==========================

import os

from supabase import create_client


# ==========================
# CONFIGURATION
# ==========================

SUPABASE_URL = os.getenv(
    "SUPABASE_URL",
    "https://uavklduzgwzdwzngtpgg.supabase.co"
)

SUPABASE_KEY = os.getenv(
    "SUPABASE_KEY",
    "sb_publishable_8FNC-V2NgSlOLEuxEx2N4Q_tcaTxaqv"
)


# ==========================
# CLIENT SUPABASE
# ==========================

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


# ==========================
# CONNEXION
# ==========================

def connexion():
    """
    Retourne le client Supabase.

    Cette fonction garde le même nom
    que l'ancien database.py afin que
    app.py puisse continuer à l'utiliser.
    """

    return supabase


# ==========================
# CREATION DE LA BASE
# ==========================

def creer_base():
    """
    Les tables existent déjà dans Supabase.

    On ne les recrée donc pas ici.
    """

    print("✅ Connexion Supabase configurée.")
    print("📦 Les tables existantes sont utilisées.")


# ==========================
# TEST DE CONNEXION
# ==========================

def tester_connexion():

    try:

        resultat = supabase.table(
            "jeux"
        ).select(
            "id"
        ).limit(1).execute()

        print(
            "✅ Supabase fonctionne correctement."
        )

        return True

    except Exception as e:

        print(
            "❌ Erreur Supabase :",
            str(e)
        )

        return False


# ==========================
# LANCEMENT DIRECT
# ==========================

if __name__ == "__main__":

    creer_base()

    tester_connexion()
