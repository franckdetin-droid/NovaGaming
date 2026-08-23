"""
=============================================================================
NOVAGAMING AUTOPILOT IA
Version Supabase + Cloudinary
=============================================================================
"""

import os
import re
import json
import sqlite3
import unicodedata
import urllib.parse
import hashlib
import time

from datetime import datetime, date, timedelta, timezone
from typing import List, Dict, Any, Optional, Tuple

import requests
from bs4 import BeautifulSoup

from supabase import create_client, Client


# =============================================================================
# CONFIGURATION
# =============================================================================

DAILY_GAME_LIMIT = 2

DEFAULT_DB_PATH = os.environ.get(
    "NOVAGAMING_DB_PATH",
    "novagaming.db"
)

DEFAULT_TIMEOUT = 12

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36 NovaGamingBot/2.0"
)

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,image/avif,*/*;q=0.8"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
}


# =============================================================================
# SUPABASE
# =============================================================================

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

supabase: Optional[Client] = None


def get_supabase() -> Client:
    global supabase

    if supabase is None:

        if not SUPABASE_URL:
            raise RuntimeError(
                "SUPABASE_URL n'est pas configurée dans Railway."
            )

        if not SUPABASE_KEY:
            raise RuntimeError(
                "SUPABASE_KEY n'est pas configurée dans Railway."
            )

        supabase = create_client(
            SUPABASE_URL,
            SUPABASE_KEY
        )

    return supabase


# =============================================================================
# CLOUDINARY
# =============================================================================

CLOUDINARY_CLOUD_NAME = os.environ.get(
    "CLOUDINARY_CLOUD_NAME",
    ""
)

CLOUDINARY_API_KEY = os.environ.get(
    "CLOUDINARY_API_KEY",
    ""
)

CLOUDINARY_API_SECRET = os.environ.get(
    "CLOUDINARY_API_SECRET",
    ""
)

CLOUDINARY_URL = os.environ.get(
    "CLOUDINARY_URL",
    ""
)


def get_cloudinary_config() -> Dict[str, str]:

    config = {
        "cloud_name": CLOUDINARY_CLOUD_NAME,
        "api_key": CLOUDINARY_API_KEY,
        "api_secret": CLOUDINARY_API_SECRET
    }

    if (
        CLOUDINARY_URL
        and not config["cloud_name"]
    ):
        try:

            parsed = urllib.parse.urlparse(
                CLOUDINARY_URL
            )

            config["cloud_name"] = (
                parsed.hostname or ""
            )

            config["api_key"] = (
                parsed.username or ""
            )

            config["api_secret"] = (
                parsed.password or ""
            )

        except Exception as e:

            print(
                f"[Cloudinary Config Warning] {e}"
            )

    return config


# =============================================================================
# UPLOAD IMAGE CLOUDINARY
# =============================================================================

def upload_image_to_cloudinary(
    image_url: str,
    slug: str
) -> str:

    if not image_url:
        return ""

    if not image_url.startswith(
        ("http://", "https://")
    ):
        return image_url

    config = get_cloudinary_config()

    if not config["cloud_name"]:
        print(
            "[Cloudinary] CLOUD_NAME absent, "
            "image originale conservée."
        )
        return image_url

    try:

        import cloudinary
        import cloudinary.uploader

        cloudinary.config(
            cloud_name=config["cloud_name"],
            api_key=config["api_key"],
            api_secret=config["api_secret"],
            secure=True
        )

        public_id = (
            "game_"
            + re.sub(
                r"[^a-zA-Z0-9_-]",
                "_",
                slug
            )[:60]
        )

        result = cloudinary.uploader.upload(
            image_url,
            folder="novagaming/autopilot",
            public_id=public_id,
            overwrite=True,
            resource_type="image"
        )

        secure_url = result.get(
            "secure_url"
        )

        if secure_url:
            print(
                f"[Cloudinary] Image uploadée : "
                f"{secure_url}"
            )

            return secure_url

    except ImportError:

        print(
            "[Cloudinary] SDK non installé."
        )

    except Exception as e:

        print(
            f"[Cloudinary SDK Error] {e}"
        )


    # -------------------------------------------------------------------------
    # FALLBACK REST CLOUDINARY
    # -------------------------------------------------------------------------

    try:

        timestamp = int(time.time())

        folder = "novagaming/autopilot"

        public_id = (
            "game_"
            + re.sub(
                r"[^a-zA-Z0-9_-]",
                "_",
                slug
            )[:60]
        )

        signature_string = (
            f"folder={folder}"
            f"&overwrite=true"
            f"&public_id={public_id}"
            f"&timestamp={timestamp}"
            f"{config['api_secret']}"
        )

        signature = hashlib.sha1(
            signature_string.encode(
                "utf-8"
            )
        ).hexdigest()

        endpoint = (
            "https://api.cloudinary.com/v1_1/"
            f"{config['cloud_name']}/image/upload"
        )

        payload = {
            "file": image_url,
            "api_key": config["api_key"],
            "timestamp": timestamp,
            "folder": folder,
            "public_id": public_id,
            "overwrite": "true",
            "signature": signature
        }

        response = requests.post(
            endpoint,
            data=payload,
            timeout=20
        )

        if response.status_code == 200:

            data = response.json()

            secure_url = data.get(
                "secure_url"
            )

            if secure_url:
                print(
                    "[Cloudinary REST] Upload réussi."
                )

                return secure_url

        print(
            "[Cloudinary REST] "
            f"HTTP {response.status_code}"
        )

    except Exception as e:

        print(
            f"[Cloudinary REST Error] {e}"
        )

    # -------------------------------------------------------------------------
    # FALLBACK URL ORIGINALE
    # -------------------------------------------------------------------------

    return image_url


# =============================================================================
# UTILITAIRES
# =============================================================================

def normalize_text(
    text: Optional[str]
) -> str:

    if not text:
        return ""

    text = unicodedata.normalize(
        "NFKD",
        text
    ).encode(
        "ASCII",
        "ignore"
    ).decode(
        "utf-8"
    )

    text = text.lower()

    text = re.sub(
        r"[^\w\s-]",
        "",
        text
    )

    text = re.sub(
        r"[\s_-]+",
        " ",
        text
    ).strip()

    return text


def generate_slug(
    text: str
) -> str:

    normalized = normalize_text(text)

    slug = re.sub(
        r"\s+",
        "-",
        normalized
    )

    return (
        slug[:120]
        if slug
        else "jeu-inconnu"
    )


def extract_domain(
    url: str
) -> str:

    try:

        parsed = urllib.parse.urlparse(
            url
        )

        domain = parsed.netloc.lower()

        if ":" in domain:
            domain = domain.split(":")[0]

        if domain.startswith("www."):
            domain = domain[4:]

        return domain

    except Exception:

        return ""


def is_domain_allowed(
    url: str,
    allowed_domains: List[str]
) -> bool:

    domain = extract_domain(url)

    if not domain:
        return False

    for allowed in allowed_domains:

        clean = allowed.strip().lower()

        if clean.startswith("www."):
            clean = clean[4:]

        if (
            domain == clean
            or domain.endswith("." + clean)
        ):
            return True

    return False
# =============================================================================
# PARTIE 2/5
# GESTION AUTOPILOT + PARTENAIRES + PARAMÈTRES + LOGS
# =============================================================================


# =============================================================================
# CONNEXION SQLITE POUR LES TABLES TECHNIQUES AUTOPILOT
# =============================================================================

def get_db_connection(
    db_path: Optional[str] = None
) -> sqlite3.Connection:

    path = db_path or DEFAULT_DB_PATH

    conn = sqlite3.connect(
        path,
        timeout=20
    )

    conn.row_factory = sqlite3.Row

    return conn


# =============================================================================
# INITIALISATION DES TABLES AUTOPILOT
# =============================================================================

def init_autopilot_db(
    db_path: Optional[str] = None
) -> None:

    conn = get_db_connection(db_path)

    cursor = conn.cursor()

    try:

        # ---------------------------------------------------------------------
        # PARTENAIRES
        # ---------------------------------------------------------------------

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS autopilot_partners (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                base_url TEXT NOT NULL UNIQUE,
                allowed_domains TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                last_scanned_at TEXT,
                total_found INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)

        # ---------------------------------------------------------------------
        # LOGS
        # ---------------------------------------------------------------------

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS autopilot_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                partner_id INTEGER,
                partner_name TEXT,
                pages_scanned INTEGER NOT NULL DEFAULT 0,
                games_detected INTEGER NOT NULL DEFAULT 0,
                duplicates_count INTEGER NOT NULL DEFAULT 0,
                invalid_links_count INTEGER NOT NULL DEFAULT 0,
                games_published_count INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL,
                details_json TEXT
            )
        """)

        # ---------------------------------------------------------------------
        # JEUX PUBLIÉS PAR AUTOPILOT
        # ---------------------------------------------------------------------

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS autopilot_published (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_title TEXT NOT NULL,
                normalized_title TEXT NOT NULL,
                slug TEXT NOT NULL,
                platform TEXT,
                category TEXT,
                image_url TEXT,
                source_url TEXT NOT NULL,
                external_url TEXT NOT NULL,
                published_date TEXT NOT NULL,
                created_at TEXT NOT NULL,
                partner_id INTEGER
            )
        """)

        # ---------------------------------------------------------------------
        # PARAMÈTRES
        # ---------------------------------------------------------------------

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS autopilot_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        cursor.execute("""
            INSERT OR IGNORE INTO
            autopilot_settings
            (key, value)
            VALUES
            ('is_enabled', '1')
        """)

        cursor.execute("""
            INSERT OR IGNORE INTO
            autopilot_settings
            (key, value)
            VALUES
            ('daily_limit', ?)
        """, (
            str(DAILY_GAME_LIMIT),
        ))

        cursor.execute("""
            INSERT OR IGNORE INTO
            autopilot_settings
            (key, value)
            VALUES
            ('last_run', '')
        """)

        cursor.execute("""
            INSERT OR IGNORE INTO
            autopilot_settings
            (key, value)
            VALUES
            ('next_run', '')
        """)

        conn.commit()

        print(
            "[AutoPilot] Tables techniques initialisées."
        )

    except Exception as e:

        conn.rollback()

        print(
            f"[AutoPilot DB Error] {e}"
        )

    finally:

        conn.close()


# Initialisation automatique
try:

    init_autopilot_db()

except Exception as e:

    print(
        f"[AutoPilot Init Warning] {e}"
    )


# =============================================================================
# PARTENAIRES
# =============================================================================

def get_all_partners(
    db_path: Optional[str] = None
) -> List[Dict[str, Any]]:

    conn = get_db_connection(db_path)

    cursor = conn.cursor()

    try:

        cursor.execute("""
            SELECT *
            FROM autopilot_partners
            ORDER BY id DESC
        """)

        rows = cursor.fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:

        conn.close()


def get_active_partners(
    db_path: Optional[str] = None
) -> List[Dict[str, Any]]:

    conn = get_db_connection(db_path)

    cursor = conn.cursor()

    try:

        cursor.execute("""
            SELECT *
            FROM autopilot_partners
            WHERE is_active = 1
            ORDER BY id ASC
        """)

        rows = cursor.fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:

        conn.close()


def add_partner(
    name: str,
    base_url: str,
    allowed_domains: Optional[str] = None,
    db_path: Optional[str] = None
) -> Tuple[bool, str]:

    clean_name = (
        name or ""
    ).strip()

    clean_url = (
        base_url or ""
    ).strip()

    if not clean_url:

        return (
            False,
            "URL du partenaire manquante."
        )

    if not clean_url.startswith(
        ("http://", "https://")
    ):

        clean_url = (
            "https://"
            + clean_url
        )

    domain = extract_domain(
        clean_url
    )

    if not domain:

        return (
            False,
            "URL de partenaire invalide."
        )

    domains = [domain]

    if allowed_domains:

        for item in allowed_domains.split(","):

            item = item.strip()

            if not item:
                continue

            item_domain = (
                extract_domain(item)
                or item.lower()
            )

            if item_domain not in domains:

                domains.append(
                    item_domain
                )

    allowed_domains_string = ",".join(
        domains
    )

    conn = get_db_connection(
        db_path
    )

    cursor = conn.cursor()

    try:

        now = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        cursor.execute("""
            INSERT INTO autopilot_partners (
                name,
                base_url,
                allowed_domains,
                is_active,
                created_at
            )
            VALUES (?, ?, ?, 1, ?)
        """, (
            clean_name or domain,
            clean_url,
            allowed_domains_string,
            now
        ))

        conn.commit()

        return (
            True,
            "Partenaire ajouté avec succès."
        )

    except sqlite3.IntegrityError:

        return (
            False,
            "Ce partenaire ou cette URL existe déjà."
        )

    except Exception as e:

        conn.rollback()

        return (
            False,
            f"Erreur lors de l'ajout : {e}"
        )

    finally:

        conn.close()


def delete_partner(
    partner_id: int,
    db_path: Optional[str] = None
) -> Tuple[bool, str]:

    conn = get_db_connection(
        db_path
    )

    cursor = conn.cursor()

    try:

        cursor.execute("""
            DELETE FROM autopilot_partners
            WHERE id = ?
        """, (
            partner_id,
        ))

        conn.commit()

        return (
            True,
            "Partenaire supprimé."
        )

    except Exception as e:

        conn.rollback()

        return (
            False,
            f"Erreur lors de la suppression : {e}"
        )

    finally:

        conn.close()


def toggle_partner(
    partner_id: int,
    db_path: Optional[str] = None
) -> Tuple[bool, str]:

    conn = get_db_connection(
        db_path
    )

    cursor = conn.cursor()

    try:

        cursor.execute("""
            SELECT is_active
            FROM autopilot_partners
            WHERE id = ?
        """, (
            partner_id,
        ))

        row = cursor.fetchone()

        if not row:

            return (
                False,
                "Partenaire introuvable."
            )

        current_status = int(
            row["is_active"]
        )

        new_status = (
            0
            if current_status == 1
            else 1
        )

        cursor.execute("""
            UPDATE autopilot_partners
            SET is_active = ?
            WHERE id = ?
        """, (
            new_status,
            partner_id
        ))

        conn.commit()

        message = (
            "Partenaire activé."
            if new_status == 1
            else
            "Partenaire désactivé."
        )

        return (
            True,
            message
        )

    except Exception as e:

        conn.rollback()

        return (
            False,
            f"Erreur : {e}"
        )

    finally:

        conn.close()


# =============================================================================
# TEST D'UN PARTENAIRE
# =============================================================================

def test_partner(
    partner_id: int,
    db_path: Optional[str] = None
) -> Dict[str, Any]:

    conn = get_db_connection(
        db_path
    )

    cursor = conn.cursor()

    try:

        cursor.execute("""
            SELECT *
            FROM autopilot_partners
            WHERE id = ?
        """, (
            partner_id,
        ))

        partner = cursor.fetchone()

    finally:

        conn.close()

    if not partner:

        return {
            "success": False,
            "message": "Partenaire introuvable."
        }

    url = partner["base_url"]

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=DEFAULT_TIMEOUT,
            allow_redirects=True
        )

        html_lower = (
            response.text.lower()
        )

        if response.status_code in (
            401,
            403
        ):

            return {
                "success": False,
                "status_code": response.status_code,
                "message": (
                    "Accès refusé par le partenaire."
                )
            }

        if (
            "captcha" in html_lower
            or (
                "cloudflare" in html_lower
                and "challenge" in html_lower
            )
        ):

            return {
                "success": False,
                "status_code": response.status_code,
                "message": (
                    "Protection technique "
                    "ou CAPTCHA détecté."
                )
            }

        return {
            "success": response.ok,
            "status_code": response.status_code,
            "response_time_ms": int(
                response.elapsed.total_seconds()
                * 1000
            ),
            "final_url": response.url,
            "message": (
                "Partenaire accessible."
                if response.ok
                else
                f"HTTP {response.status_code}"
            )
        }

    except requests.exceptions.Timeout:

        return {
            "success": False,
            "message": "Timeout."
        }

    except requests.exceptions.RequestException as e:

        return {
            "success": False,
            "message": (
                f"Erreur réseau : {str(e)[:100]}"
            )
        }


# =============================================================================
# PARAMÈTRES AUTOPILOT
# =============================================================================

def get_setting(
    key: str,
    default: str = "",
    db_path: Optional[str] = None
) -> str:

    conn = get_db_connection(
        db_path
    )

    cursor = conn.cursor()

    try:

        cursor.execute("""
            SELECT value
            FROM autopilot_settings
            WHERE key = ?
        """, (
            key,
        ))

        row = cursor.fetchone()

        if row:

            return str(
                row["value"]
            )

        return default

    finally:

        conn.close()


def set_setting(
    key: str,
    value: str,
    db_path: Optional[str] = None
) -> bool:

    conn = get_db_connection(
        db_path
    )

    cursor = conn.cursor()

    try:

        cursor.execute("""
            INSERT INTO autopilot_settings
            (key, value)
            VALUES (?, ?)
            ON CONFLICT(key)
            DO UPDATE SET value = excluded.value
        """, (
            key,
            str(value)
        ))

        conn.commit()

        return True

    except Exception as e:

        conn.rollback()

        print(
            f"[AutoPilot Setting Error] {e}"
        )

        return False

    finally:

        conn.close()


# =============================================================================
# ACTIVATION / DÉSACTIVATION
# =============================================================================

def toggle_autopilot_status(
    enable: Optional[bool] = None,
    db_path: Optional[str] = None
) -> bool:

    current = (
        get_setting(
            "is_enabled",
            "1",
            db_path
        ) == "1"
    )

    if enable is None:

        new_status = not current

    else:

        new_status = bool(
            enable
        )

    set_setting(
        "is_enabled",
        "1" if new_status else "0",
        db_path
    )

    return new_status


# =============================================================================
# COMPTEUR DU JOUR
# =============================================================================

def get_today_published_count(
    db_path: Optional[str] = None
) -> int:

    today = date.today().isoformat()

    conn = get_db_connection(
        db_path
    )

    cursor = conn.cursor()

    try:

        cursor.execute("""
            SELECT COUNT(*)
            FROM autopilot_published
            WHERE published_date = ?
        """, (
            today,
        ))

        row = cursor.fetchone()

        return int(
            row[0] if row else 0
        )

    finally:

        conn.close()


# =============================================================================
# LOG AUTOPILOT
# =============================================================================

def save_autopilot_log(
    *,
    pages_scanned: int = 0,
    games_detected: int = 0,
    duplicates: int = 0,
    invalid_links: int = 0,
    games_published: int = 0,
    status: str = "UNKNOWN",
    details: Optional[Dict[str, Any]] = None,
    partner_id: Optional[int] = None,
    partner_name: str = "Tous les partenaires",
    db_path: Optional[str] = None
) -> None:

    conn = get_db_connection(
        db_path
    )

    cursor = conn.cursor()

    try:

        timestamp = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        details_json = json.dumps(
            details or {},
            ensure_ascii=False
        )

        cursor.execute("""
            INSERT INTO autopilot_logs (
                timestamp,
                partner_id,
                partner_name,
                pages_scanned,
                games_detected,
                duplicates_count,
                invalid_links_count,
                games_published_count,
                status,
                details_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            timestamp,
            partner_id,
            partner_name,
            pages_scanned,
            games_detected,
            duplicates,
            invalid_links,
            games_published,
            status,
            details_json
        ))

        conn.commit()

    except Exception as e:

        conn.rollback()

        print(
            f"[AutoPilot Log Error] {e}"
        )

    finally:

        conn.close()
        # =============================================================================
# NOVAGAMING AUTOPILOT IA - PARTIE 3/5
# ANALYSE DES PARTENAIRES + DÉTECTION DES JEUX
# SUPABASE + CLOUDINARY
# =============================================================================

import re
import urllib.parse
from typing import Optional, Dict, Any, List, Tuple

import requests
from bs4 import BeautifulSoup


# =============================================================================
# UTILITAIRES URL / DOMAINE
# =============================================================================

def extract_domain(url: str) -> str:
    """Extrait le domaine principal d'une URL."""
    try:
        parsed = urllib.parse.urlparse(url)
        domain = parsed.netloc.lower()

        if ":" in domain:
            domain = domain.split(":")[0]

        if domain.startswith("www."):
            domain = domain[4:]

        return domain
    except Exception:
        return ""


def is_domain_allowed(
    url: str,
    allowed_domains: List[str]
) -> bool:
    """Vérifie qu'une URL appartient à un domaine autorisé."""

    domain = extract_domain(url)

    if not domain:
        return False

    for allowed in allowed_domains:

        allowed = allowed.strip().lower()

        if allowed.startswith("www."):
            allowed = allowed[4:]

        if domain == allowed:
            return True

        if domain.endswith("." + allowed):
            return True

    return False


# =============================================================================
# NORMALISATION
# =============================================================================

def normalize_text(text: Optional[str]) -> str:
    """Normalise un texte pour l'anti-doublon."""

    if not text:
        return ""

    import unicodedata

    text = unicodedata.normalize(
        "NFKD",
        text
    ).encode(
        "ASCII",
        "ignore"
    ).decode("utf-8")

    text = text.lower()

    text = re.sub(
        r"[^\w\s-]",
        "",
        text
    )

    text = re.sub(
        r"[\s_-]+",
        " ",
        text
    ).strip()

    return text


def generate_slug(text: str) -> str:
    """Crée un slug propre."""

    normalized = normalize_text(text)

    slug = re.sub(
        r"\s+",
        "-",
        normalized
    )

    return slug[:120] or "jeu-inconnu"


# =============================================================================
# VALIDATION DU LIEN DE TÉLÉCHARGEMENT
# =============================================================================

def validate_external_link(
    url: str,
    allowed_domains: List[str]
) -> Tuple[bool, str]:

    if not url:
        return False, "URL vide"

    if not url.startswith(
        ("http://", "https://")
    ):
        return False, "URL invalide"

    if not is_domain_allowed(
        url,
        allowed_domains
    ):
        return (
            False,
            f"Domaine non autorisé : {extract_domain(url)}"
        )

    try:

        response = requests.head(
            url,
            headers=HEADERS,
            timeout=8,
            allow_redirects=True
        )

        # Certains serveurs refusent HEAD.
        if response.status_code == 405:

            response = requests.get(
                url,
                headers=HEADERS,
                timeout=8,
                allow_redirects=True,
                stream=True
            )

            response.close()

        if response.status_code not in (
            200,
            301,
            302,
            307,
            308
        ):
            return (
                False,
                f"Code HTTP : {response.status_code}"
            )

        final_url = response.url

        if not is_domain_allowed(
            final_url,
            allowed_domains
        ):
            return (
                False,
                f"Redirection vers domaine non autorisé : "
                f"{extract_domain(final_url)}"
            )

        return True, "Valide"

    except requests.exceptions.Timeout:

        return False, "Timeout"

    except requests.exceptions.RequestException as e:

        return (
            False,
            f"Erreur réseau : {str(e)[:80]}"
        )


# =============================================================================
# DÉTECTION DE LA PLATEFORME
# =============================================================================

def detect_platform(
    title: str,
    platform_text: str,
    full_text: str
) -> str:

    text = (
        f"{title} "
        f"{platform_text} "
        f"{full_text}"
    ).lower()

    if (
        "psp" in text
        or "ppsspp" in text
    ):
        return "PPSSPP"

    if (
        "ps2" in text
        or "playstation 2" in text
    ):
        return "PS2"

    if "ps5" in text:
        return "PS5"

    if "ps4" in text:
        return "PS4"

    if "xbox" in text:
        return "Xbox"

    if "switch" in text:
        return "Nintendo Switch"

    if "android" in text:
        return "Android"

    if "pc" in text:
        return "PC"

    return "PC"


# =============================================================================
# EXTRACTION D'UNE FICHE DE JEU
# =============================================================================

def parse_game_card(
    soup_element,
    base_url: str,
    allowed_domains: List[str]
) -> Optional[Dict[str, Any]]:

    try:

        # -------------------------------------------------
        # TITRE
        # -------------------------------------------------

        title_el = (
            soup_element.find(
                ["h1", "h2", "h3", "h4"]
            )
            or soup_element.find(
                class_=re.compile(
                    r"(title|titre|game-name|name)",
                    re.I
                )
            )
        )

        title = (
            title_el.get_text(
                " ",
                strip=True
            )
            if title_el
            else ""
        )

        if not title or len(title) < 2:
            return None

        # -------------------------------------------------
        # DESCRIPTION
        # -------------------------------------------------

        desc_el = (
            soup_element.find(
                class_=re.compile(
                    r"(desc|description|excerpt|summary|info|details|story)",
                    re.I
                )
            )
            or soup_element.find("p")
        )

        description = (
            desc_el.get_text(
                " ",
                strip=True
            )
            if desc_el
            else
            f"Découvrez {title} sur NovaGaming."
        )

        # -------------------------------------------------
        # PLATEFORME
        # -------------------------------------------------

        platform_el = soup_element.find(
            class_=re.compile(
                r"(platform|plateforme|system|support)",
                re.I
            )
        )

        platform_text = (
            platform_el.get_text(
                " ",
                strip=True
            )
            if platform_el
            else ""
        )

        full_text = soup_element.get_text(
            " ",
            strip=True
        )

        platform = detect_platform(
            title,
            platform_text,
            full_text
        )

        # -------------------------------------------------
        # CATÉGORIE
        # -------------------------------------------------

        category_el = soup_element.find(
            class_=re.compile(
                r"(category|categorie|genre|tag|type)",
                re.I
            )
        )

        category = (
            category_el.get_text(
                " ",
                strip=True
            )
            if category_el
            else "Action"
        )

        if not category:
            category = "Action"

        # -------------------------------------------------
        # IMAGE
        # -------------------------------------------------

        image_url = ""

        img = soup_element.find("img")

        if img:

            raw_img = (
                img.get("src")
                or img.get("data-src")
                or img.get("data-lazy-src")
                or img.get("data-original")
                or ""
            )

            if raw_img:

                image_url = urllib.parse.urljoin(
                    base_url,
                    raw_img
                )

        # -------------------------------------------------
        # LIENS
        # -------------------------------------------------

        source_url = base_url
        external_url = ""

        links = soup_element.find_all(
            "a",
            href=True
        )

        for link in links:

            href = link.get(
                "href",
                ""
            ).strip()

            if not href:
                continue

            full_href = urllib.parse.urljoin(
                base_url,
                href
            )

            link_text = link.get_text(
                " ",
                strip=True
            ).lower()

            classes = " ".join(
                link.get(
                    "class",
                    []
                )
            ).lower()

            href_lower = full_href.lower()

            download_keywords = (
                "download",
                "télécharger",
                "telecharger",
                "download",
                "lien",
                "link",
                "get",
                "play"
            )

            is_download_link = any(
                keyword in link_text
                or keyword in classes
                or keyword in href_lower
                for keyword in download_keywords
            )

            if is_download_link:

                if not external_url:
                    external_url = full_href

            elif source_url == base_url:

                source_url = full_href

        # -------------------------------------------------
        # FALLBACK LIEN
        # -------------------------------------------------

        if not external_url:

            for link in links:

                href = link.get(
                    "href",
                    ""
                ).strip()

                if href:

                    candidate = urllib.parse.urljoin(
                        base_url,
                        href
                    )

                    if candidate != base_url:
                        external_url = candidate
                        break

        if not external_url:
            return None

        # -------------------------------------------------
        # SLUG
        # -------------------------------------------------

        slug = generate_slug(title)

        normalized_title = normalize_text(
            title
        )

        return {
            "title": title[:200],

            "normalized_title":
                normalized_title,

            "slug":
                slug,

            "description":
                description[:1000],

            "platform":
                platform,

            "category":
                category[:100],

            "raw_image_url":
                image_url,

            "image_url":
                image_url,

            "source_url":
                source_url,

            "external_url":
                external_url
        }

    except Exception as e:

        print(
            "[AutoPilot Parse Error]",
            e
        )

        return None


# =============================================================================
# ANALYSE D'UN PARTENAIRE
# =============================================================================

def scan_partner_site(
    partner: Dict[str, Any]
) -> Dict[str, Any]:

    base_url = partner.get(
        "base_url",
        ""
    )

    partner_id = partner.get(
        "id"
    )

    partner_name = partner.get(
        "name",
        "Partenaire"
    )

    allowed_domains = [
        d.strip()
        for d in (
            partner.get(
                "allowed_domains"
            )
            or ""
        ).split(",")
        if d.strip()
    ]

    if not allowed_domains:

        domain = extract_domain(
            base_url
        )

        if domain:
            allowed_domains = [domain]

    result = {

        "partner_id":
            partner_id,

        "partner_name":
            partner_name,

        "pages_scanned":
            0,

        "games_detected":
            0,

        "duplicates":
            0,

        "invalid_links":
            0,

        "candidates":
            [],

        "errors":
            []
    }

    if not base_url:

        result["errors"].append(
            "URL du partenaire absente."
        )

        return result

    try:

        print(
            f"[AutoPilot] Analyse : {base_url}"
        )

        response = requests.get(
            base_url,
            headers=HEADERS,
            timeout=DEFAULT_TIMEOUT,
            allow_redirects=True
        )

        result["pages_scanned"] += 1

        if response.status_code != 200:

            result["errors"].append(
                f"HTTP {response.status_code}"
            )

            return result

        html_lower = response.text.lower()

        if (
            "captcha" in html_lower
            or (
                "cloudflare" in html_lower
                and "challenge" in html_lower
            )
        ):

            result["errors"].append(
                "CAPTCHA/Cloudflare détecté."
            )

            return result

        soup = BeautifulSoup(
            response.content,
            "html.parser"
        )

        # -------------------------------------------------
        # RECHERCHE DES CARTES
        # -------------------------------------------------

        containers = soup.find_all(
            class_=re.compile(
                r"(game|jeu|item|card|entry|post|article|product)",
                re.I
            )
        )

        if not containers:

            containers = soup.find_all(
                "article"
            )

        if not containers:

            containers = soup.find_all(
                ["div", "section"]
            )

        detected_games = []

        for container in containers:

            game = parse_game_card(
                container,
                base_url,
                allowed_domains
            )

            if not game:
                continue

            normalized = game.get(
                "normalized_title",
                ""
            )

            if not normalized:
                continue

            # Anti-doublon dans le scan actuel
            if any(
                g.get(
                    "normalized_title"
                ) == normalized
                for g in detected_games
            ):
                continue

            detected_games.append(
                game
            )

        result["games_detected"] = len(
            detected_games
        )

        print(
            f"[AutoPilot] {len(detected_games)} "
            f"jeu(x) détecté(s) sur {partner_name}"
        )

        # -------------------------------------------------
        # VALIDATION DES CANDIDATS
        # -------------------------------------------------

        for game in detected_games:

            try:

                # is_game_duplicate() sera défini
                # dans la partie 4.

                if is_game_duplicate(
                    game
                ):

                    result["duplicates"] += 1

                    continue

            except Exception as e:

                print(
                    "[AutoPilot Duplicate Check]",
                    e
                )

            valid, reason = validate_external_link(
                game["external_url"],
                allowed_domains
            )

            if not valid:

                result[
                    "invalid_links"
                ] += 1

                result[
                    "errors"
                ].append(
                    f"{game['title']} : {reason}"
                )

                continue

            game["partner_id"] = partner_id
            game["partner_name"] = partner_name

            result[
                "candidates"
            ].append(game)

    except requests.exceptions.Timeout:

        result["errors"].append(
            f"Timeout : {base_url}"
        )

    except requests.exceptions.RequestException as e:

        result["errors"].append(
            f"Erreur réseau : {str(e)[:100]}"
        )

    except Exception as e:

        result["errors"].append(
            f"Erreur analyse : {str(e)[:100]}"
        )

        print(
            "[AutoPilot Scan Error]",
            e
        )

    return result


# =============================================================================
# TEST D'UN PARTENAIRE
# =============================================================================

def test_partner(
    partner_id: int,
    db_path: Optional[str] = None
) -> Dict[str, Any]:

    try:

        partner = get_all_partners(
            db_path
        )

        partner = next(
            (
                p for p in partner
                if int(p["id"]) == int(partner_id)
            ),
            None
        )

        if not partner:

            return {
                "success": False,
                "message":
                    "Partenaire introuvable."
            }

        url = partner[
            "base_url"
        ]

        start = datetime.now()

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=DEFAULT_TIMEOUT,
            allow_redirects=True
        )

        elapsed = (
            datetime.now() - start
        ).total_seconds() * 1000

        html_lower = response.text.lower()

        if (
            "captcha" in html_lower
            or (
                "cloudflare" in html_lower
                and "challenge" in html_lower
            )
        ):

            return {
                "success": False,
                "status_code":
                    response.status_code,
                "message":
                    "Protection CAPTCHA/Cloudflare détectée."
            }

        return {

            "success":
                response.status_code == 200,

            "status_code":
                response.status_code,

            "response_time_ms":
                int(elapsed),

            "final_url":
                response.url,

            "message":
                (
                    "Partenaire accessible."
                    if response.status_code == 200
                    else
                    f"HTTP {response.status_code}"
                )
        }

    except requests.exceptions.Timeout:

        return {
            "success": False,
            "message":
                "Timeout du partenaire."
        }

    except requests.exceptions.RequestException as e:

        return {
            "success": False,
            "message":
                f"Erreur réseau : {str(e)[:100]}"
        }

    except Exception as e:

        return {
            "success": False,
            "message":
                f"Erreur : {str(e)[:100]}"
            # =============================================================================
# NOVAGAMING AUTOPILOT IA - PARTIE 4/5
# ANTI-DOUBLON + PUBLICATION SUPABASE + CLOUDINARY
# =============================================================================

from datetime import datetime, date
from typing import Optional, Dict, Any


# =============================================================================
# SUPABASE
# =============================================================================

def get_supabase_client():
    """
    Retourne le client Supabase configuré avec les variables Railway.
    Variables nécessaires :
        SUPABASE_URL
        SUPABASE_KEY
    """

    try:
        from supabase import create_client

        supabase_url = os.environ.get(
            "SUPABASE_URL",
            ""
        ).strip()

        supabase_key = os.environ.get(
            "SUPABASE_KEY",
            ""
        ).strip()

        if not supabase_url:
            raise RuntimeError(
                "SUPABASE_URL n'est pas configurée."
            )

        if not supabase_key:
            raise RuntimeError(
                "SUPABASE_KEY n'est pas configurée."
            )

        return create_client(
            supabase_url,
            supabase_key
        )

    except ImportError:
        raise RuntimeError(
            "Le package supabase n'est pas installé."
        )


# =============================================================================
# CLOUDINARY
# =============================================================================

def get_cloudinary():
    """
    Configure Cloudinary avec les variables Railway.
    """

    try:

        import cloudinary

        cloud_name = os.environ.get(
            "CLOUDINARY_CLOUD_NAME",
            ""
        ).strip()

        api_key = os.environ.get(
            "CLOUDINARY_API_KEY",
            ""
        ).strip()

        api_secret = os.environ.get(
            "CLOUDINARY_API_SECRET",
            ""
        ).strip()

        cloudinary_url = os.environ.get(
            "CLOUDINARY_URL",
            ""
        ).strip()

        if cloudinary_url:

            cloudinary.config(
                cloudinary_url=cloudinary_url,
                secure=True
            )

        elif (
            cloud_name
            and api_key
            and api_secret
        ):

            cloudinary.config(
                cloud_name=cloud_name,
                api_key=api_key,
                api_secret=api_secret,
                secure=True
            )

        else:

            return None

        return cloudinary

    except Exception as e:

        print(
            f"[Cloudinary Config Error] {e}"
        )

        return None


# =============================================================================
# UPLOAD IMAGE CLOUDINARY
# =============================================================================

def upload_image_to_cloudinary(
    image_url: str,
    slug: str
) -> str:

    """
    Télécharge l'image distante et la stocke sur Cloudinary.

    En cas d'échec, l'URL originale est conservée.
    """

    if not image_url:
        return ""

    if not image_url.startswith(
        ("http://", "https://")
    ):
        return image_url

    cloudinary = get_cloudinary()

    if not cloudinary:
        print(
            "[Cloudinary] Configuration absente."
        )

        return image_url

    try:

        import cloudinary.uploader

        result = cloudinary.uploader.upload(
            image_url,
            folder="novagaming/autopilot",
            public_id=f"game_{slug[:80]}",
            overwrite=True,
            resource_type="image",
            transformation=[
                {
                    "width": 1000,
                    "height": 1000,
                    "crop": "limit"
                },
                {
                    "quality": "auto",
                    "fetch_format": "auto"
                }
            ]
        )

        secure_url = result.get(
            "secure_url"
        )

        if secure_url:

            print(
                f"[Cloudinary] Image uploadée : {slug}"
            )

            return secure_url

    except Exception as e:

        print(
            f"[Cloudinary Upload Error] {e}"
        )

    # Fallback
    return image_url


# =============================================================================
# RECHERCHE DES JEUX DANS SUPABASE
# =============================================================================

def get_existing_games(
    supabase=None
):

    if supabase is None:
        supabase = get_supabase_client()

    try:

        response = (
            supabase
            .table("jeux")
            .select(
                "id,nom,console,lien,couverture"
            )
            .execute()
        )

        return response.data or []

    except Exception as e:

        print(
            f"[Supabase Games Error] {e}"
        )

        return []


# =============================================================================
# ANTI-DOUBLON
# =============================================================================

def is_game_duplicate(
    game: Dict[str, Any],
    db_path: Optional[str] = None
) -> bool:

    """
    Vérifie si le jeu existe déjà dans Supabase.

    Critères :
    - nom
    - slug si disponible
    - lien de téléchargement
    """

    try:

        supabase = get_supabase_client()

        title = (
            game.get("title")
            or game.get("nom")
            or ""
        ).strip()

        normalized_title = normalize_text(
            title
        )

        external_url = (
            game.get("external_url")
            or game.get("lien")
            or ""
        ).strip()

        if not title:
            return True

        # -------------------------------------------------
        # Vérification par nom
        # -------------------------------------------------

        response = (
            supabase
            .table("jeux")
            .select("id,nom")
            .ilike(
                "nom",
                title
            )
            .limit(20)
            .execute()
        )

        for row in (
            response.data or []
        ):

            existing_name = (
                row.get("nom")
                or ""
            )

            if normalize_text(
                existing_name
            ) == normalized_title:

                print(
                    f"[AutoPilot] Doublon trouvé : {title}"
                )

                return True

        # -------------------------------------------------
        # Vérification par lien
        # -------------------------------------------------

        if external_url:

            response = (
                supabase
                .table("jeux")
                .select("id,lien")
                .eq(
                    "lien",
                    external_url
                )
                .limit(1)
                .execute()
            )

            if response.data:

                print(
                    "[AutoPilot] "
                    "Lien déjà présent."
                )

                return True

        return False

    except Exception as e:

        print(
            f"[AutoPilot Duplicate Error] {e}"
        )

        # On ne considère pas automatiquement
        # le jeu comme doublon en cas d'erreur.
        return False


# =============================================================================
# AJOUT D'UNE NOTIFICATION
# =============================================================================

def create_game_notification(
    title: str
):

    try:

        supabase = get_supabase_client()

        notification = {
            "titre":
                f"Nouveau jeu disponible : {title}",

            "message":
                f"{title} vient d'être ajouté au catalogue NovaGaming.",

            "lu":
                0,

            "date":
                datetime.utcnow().isoformat()
        }

        response = (
            supabase
            .table("notifications")
            .insert(notification)
            .execute()
        )

        print(
            f"[AutoPilot] Notification créée : {title}"
        )

        return bool(
            response.data
        )

    except Exception as e:

        print(
            f"[Notification Error] {e}"
        )

        return False


# =============================================================================
# PUBLICATION DANS SUPABASE
# =============================================================================

def publish_game(
    game: Dict[str, Any],
    db_path: Optional[str] = None
) -> bool:

    """
    Publie automatiquement un jeu dans Supabase.

    Table utilisée :
        jeux

    Colonnes connues de ta BDD :
        nom
        console
        description
        taille
        version
        langue
        couverture
        image1 ... image10
        lien
        telechargements
        date_ajout
    """

    try:

        supabase = get_supabase_client()

        title = (
            game.get("title")
            or game.get("nom")
            or ""
        ).strip()

        if not title:

            print(
                "[AutoPilot] Jeu sans nom."
            )

            return False

        # -------------------------------------------------
        # ANTI-DOUBLON AVANT INSERTION
        # -------------------------------------------------

        if is_game_duplicate(
            game,
            db_path
        ):

            print(
                f"[AutoPilot] Publication annulée : "
                f"doublon {title}"
            )

            return False

        # -------------------------------------------------
        # IMAGE PRINCIPALE
        # -------------------------------------------------

        raw_image = (
            game.get("raw_image_url")
            or game.get("image_url")
            or ""
        )

        couverture = ""

        if raw_image:

            couverture = upload_image_to_cloudinary(
                raw_image,
                game.get(
                    "slug",
                    generate_slug(title)
                )
            )

        # -------------------------------------------------
        # CONSOLE
        # -------------------------------------------------

        platform = (
            game.get("platform")
            or "PC"
        )

        # Conversion pour NovaGaming
        platform_upper = platform.upper()

        if "PPSSPP" in platform_upper:
            console = "Ppsspp"

        elif "PSP" in platform_upper:
            console = "Ppsspp"

        elif "PS2" in platform_upper:
            console = "PS2"

        elif "PS5" in platform_upper:
            console = "PS5"

        elif "PS4" in platform_upper:
            console = "PS4"

        elif "ANDROID" in platform_upper:
            console = "Android"

        elif "XBOX" in platform_upper:
            console = "Xbox"

        elif "SWITCH" in platform_upper:
            console = "Nintendo Switch"

        else:
            console = platform

        # -------------------------------------------------
        # DONNÉES SUPABASE
        # -------------------------------------------------

        game_data = {

            "nom":
                title,

            "console":
                console[:100],

            "description":
                (
                    game.get("description")
                    or
                    f"Découvrez {title} sur NovaGaming."
                )[:2000],

            "taille":
                game.get(
                    "taille",
                    ""
                ),

            "version":
                game.get(
                    "version",
                    console
                ),

            "langue":
                game.get(
                    "langue",
                    "Anglais"
                ),

            "couverture":
                couverture,

            "image1":
                couverture,

            "image2":
                "",

            "image3":
                "",

            "image4":
                "",

            "image5":
                "",

            "image6":
                "",

            "image7":
                "",

            "image8":
                "",

            "image9":
                "",

            "image10":
                "",

            "lien":
                game.get(
                    "external_url",
                    ""
                ),

            "telechargements":
                0,

            "date_ajout":
                datetime.utcnow().isoformat()
        }

        # -------------------------------------------------
        # INSERTION
        # -------------------------------------------------

        response = (
            supabase
            .table("jeux")
            .insert(game_data)
            .execute()
        )

        if not response.data:

            print(
                "[AutoPilot] "
                "Supabase n'a retourné aucune donnée."
            )

            return False

        created_game = response.data[0]

        print(
            f"[AutoPilot] Jeu publié : "
            f"{created_game.get('nom', title)}"
        )

        # -------------------------------------------------
        # NOTIFICATION
        # -------------------------------------------------

        create_game_notification(
            title
        )

        return True

    except Exception as e:

        print(
            f"[AutoPilot Publish Error] {e}"
        )

        return False


# =============================================================================
# COMPTEUR DES JEUX PUBLIÉS PAR L'AUTOPILOT
# =============================================================================

def get_today_published_count(
    db_path: Optional[str] = None
) -> int:

    """
    Le compteur est maintenant conservé dans autopilot_published
    si cette table existe encore.

    Cette fonction ne touche pas à la table 'jeux'.
    """

    try:

        # Si ton AutoPilot utilise encore sa table
        # de suivi locale, on la conserve.
        conn = sqlite3.connect(
            db_path
            or os.environ.get(
                "NOVAGAMING_DB_PATH",
                "novagaming.db"
            )
        )

        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS autopilot_published (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_title TEXT NOT NULL,
                normalized_title TEXT NOT NULL,
                slug TEXT NOT NULL,
                published_date TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        today = date.today().isoformat()

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM autopilot_published
            WHERE published_date = ?
            """,
            (today,)
        )

        result = cursor.fetchone()

        conn.close()

        return int(
            result[0]
            if result
            else 0
        )

    except Exception as e:

        print(
            f"[AutoPilot Counter Error] {e}"
        )

        return 0


# =============================================================================
# ENREGISTRER UNE PUBLICATION AUTOPILOT
# =============================================================================

def register_autopilot_publication(
    game: Dict[str, Any],
    db_path: Optional[str] = None
):

    try:

        conn = sqlite3.connect(
            db_path
            or os.environ.get(
                "NOVAGAMING_DB_PATH",
                "novagaming.db"
            )
        )

        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS autopilot_published (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_title TEXT NOT NULL,
                normalized_title TEXT NOT NULL,
                slug TEXT NOT NULL,
                published_date TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        now = datetime.now()

        cursor.execute(
            """
            INSERT INTO autopilot_published (
                game_title,
                normalized_title,
                slug,
                published_date,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                game.get("title", ""),
                normalize_text(
                    game.get("title", "")
                ),
                game.get(
                    "slug",
                    generate_slug(
                        game.get(
                            "title",
                            "jeu"
                        )
                    )
                ),
                now.date().isoformat(),
                now.strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            )
        )

        conn.commit()
        conn.close()

        return True

    except Exception as e:

        print(
            f"[AutoPilot Register Error] {e}"
        )

        return False


# =============================================================================
# PUBLICATION SÉCURISÉE
# =============================================================================

def publish_game_and_register(
    game: Dict[str, Any],
    db_path: Optional[str] = None
) -> bool:

    """
    Publie dans Supabase puis enregistre
    la publication pour la limite quotidienne.
    """

    success = publish_game(
        game,
        db_path
    )

    if not success:
        return False

    register_autopilot_publication(
        game,
        db_path
    )

    return True
    
    }
    # =============================================================================
# 5A - PUBLICATION SUPABASE + CLOUDINARY
# =============================================================================

def get_supabase_client():
    """
    Retourne le client Supabase configuré avec les variables Railway.
    Variables nécessaires :
        SUPABASE_URL
        SUPABASE_KEY
    """
    try:
        from supabase import create_client

        url = os.environ.get("SUPABASE_URL", "").strip()
        key = os.environ.get("SUPABASE_KEY", "").strip()

        if not url or not key:
            raise RuntimeError(
                "SUPABASE_URL ou SUPABASE_KEY est manquant."
            )

        return create_client(url, key)

    except Exception as e:
        raise RuntimeError(
            f"Impossible de connecter Supabase : {e}"
        )


def supabase_table_exists(table_name: str) -> bool:
    """
    Vérifie indirectement qu'une table Supabase est accessible.
    """
    try:
        supabase = get_supabase_client()

        response = (
            supabase
            .table(table_name)
            .select("*")
            .limit(1)
            .execute()
        )

        return response is not None

    except Exception as e:
        print(
            f"[AutoPilot Supabase] Table '{table_name}' inaccessible : {e}"
        )
        return False


def get_game_columns():
    """
    Colonnes connues de la table 'jeux'.

    D'après ta structure Supabase actuelle :
        id
        nom
        console
        description
        taille
        version
        langue
        couverture
        image1 ... image10
        lien
        telechargements
        date_ajout
    """

    return {
        "id",
        "nom",
        "console",
        "description",
        "taille",
        "version",
        "langue",
        "couverture",
        "image1",
        "image2",
        "image3",
        "image4",
        "image5",
        "image6",
        "image7",
        "image8",
        "image9",
        "image10",
        "lien",
        "telechargements",
        "date_ajout",
    }


def game_exists_supabase(
    title: str,
    external_url: str = ""
) -> bool:
    """
    Anti-doublon directement dans Supabase.
    """

    try:
        supabase = get_supabase_client()

        title_clean = title.strip()

        response = (
            supabase
            .table("jeux")
            .select("id,nom,lien")
            .eq("nom", title_clean)
            .limit(1)
            .execute()
        )

        if response.data:
            return True

        if external_url:
            response = (
                supabase
                .table("jeux")
                .select("id,nom,lien")
                .eq("lien", external_url.strip())
                .limit(1)
                .execute()
            )

            if response.data:
                return True

        return False

    except Exception as e:
        print(
            f"[AutoPilot Supabase Duplicate Warning] {e}"
        )
        return False


def publish_game_supabase(
    game: Dict[str, Any]
) -> Tuple[bool, str]:
    """
    Publie réellement le jeu dans la table Supabase 'jeux'.

    Cloudinary est utilisé pour la couverture et les images.
    """

    try:
        supabase = get_supabase_client()

        title = (
            game.get("title")
            or game.get("name")
            or "Jeu inconnu"
        ).strip()

        external_url = (
            game.get("external_url")
            or game.get("download_url")
            or game.get("lien")
            or ""
        ).strip()

        if not title:
            return False, "Nom du jeu manquant."

        if not external_url:
            return False, "Lien de téléchargement manquant."

        # ---------------------------------------------------------
        # ANTI-DOUBLON SUPABASE
        # ---------------------------------------------------------

        if game_exists_supabase(
            title,
            external_url
        ):
            return False, f"Jeu déjà présent : {title}"

        # ---------------------------------------------------------
        # IMAGE / CLOUDINARY
        # ---------------------------------------------------------

        raw_image = (
            game.get("raw_image_url")
            or game.get("image_url")
            or ""
        ).strip()

        final_image = raw_image

        if raw_image.startswith(
            ("http://", "https://")
        ):
            try:
                final_image = upload_image_to_cloudinary(
                    raw_image,
                    game.get("slug") or generate_slug(title)
                )
            except Exception as e:
                print(
                    f"[Cloudinary Warning] {e}"
                )
                final_image = raw_image

        # ---------------------------------------------------------
        # CONVERSION DES DONNÉES
        # ---------------------------------------------------------

        console = (
            game.get("platform")
            or game.get("console")
            or "PC"
        ).strip()

        description = (
            game.get("description")
            or f"Découvrez {title} sur NovaGaming."
        ).strip()

        category = (
            game.get("category")
            or game.get("genre")
            or "Action"
        ).strip()

        langue = (
            game.get("langue")
            or game.get("language")
            or "Français"
        ).strip()

        version = (
            game.get("version")
            or console
        ).strip()

        taille = (
            game.get("taille")
            or game.get("size")
            or ""
        ).strip()

        now_iso = datetime.utcnow().isoformat()

        # ---------------------------------------------------------
        # DONNÉES SUPABASE
        # ---------------------------------------------------------

        payload = {
            "nom": title,
            "console": console,
            "description": description[:2000],
            "taille": taille[:100],
            "version": version[:100],
            "langue": langue[:100],
            "couverture": final_image,
            "image1": final_image,
            "image2": "",
            "image3": "",
            "image4": "",
            "image5": "",
            "image6": "",
            "image7": "",
            "image8": "",
            "image9": "",
            "image10": "",
            "lien": external_url,
            "telechargements": 0,
            "date_ajout": now_iso,
        }

        # ---------------------------------------------------------
        # INSERTION SUPABASE
        # ---------------------------------------------------------

        response = (
            supabase
            .table("jeux")
            .insert(payload)
            .execute()
        )

        if not response.data:
            return False, (
                "Supabase n'a retourné aucune donnée "
                "après l'insertion."
            )

        inserted_game = response.data[0]

        print(
            f"[AutoPilot] Jeu publié dans Supabase : "
            f"{inserted_game.get('nom', title)}"
        )

        return True, "Jeu publié avec succès."

    except Exception as e:

        print(
            f"[AutoPilot Supabase Publish Error] {e}"
        )

        return False, str(e)


# =============================================================================
# PUBLICATION AUTOPILOT COMPATIBLE AVEC L'ANCIEN SYSTÈME
# =============================================================================

def publish_game(game: Dict[str, Any], db_path: Optional[str] = None) -> bool:
    """
    Fonction principale conservée pour ne pas casser
    run_daily_autopilot().

    Elle publie maintenant dans Supabase.
    Cloudinary gère les images.
    """

    success, message = publish_game_supabase(game)

    if not success:
        print(
            f"[AutoPilot Publication] {message}"
        )
        return False

    # ---------------------------------------------------------
    # JOURNAL LOCAL AUTOPILOT
    # ---------------------------------------------------------

    try:
        conn = get_db_connection(db_path)
        cursor = conn.cursor()

        today_str = date.today().isoformat()
        now_str = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        cursor.execute("""
            INSERT INTO autopilot_published (
                game_title,
                normalized_title,
                slug,
                platform,
                category,
                image_url,
                source_url,
                external_url,
                published_date,
                created_at,
                partner_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            game.get("title", ""),
            game.get(
                "normalized_title",
                normalize_text(
                    game.get("title", "")
                )
            ),
            game.get(
                "slug",
                generate_slug(
                    game.get("title", "")
                )
            ),
            game.get("platform", "PC"),
            game.get("category", "Action"),
            game.get(
                "image_url",
                game.get("raw_image_url", "")
            ),
            game.get("source_url", ""),
            game.get("external_url", ""),
            today_str,
            now_str,
            game.get("partner_id"),
        ))

        conn.commit()
        conn.close()

    except Exception as e:

        print(
            f"[AutoPilot Log Warning] {e}"
        )

    return True
    # =============================================================================
# 5B - CYCLE AUTOPILOT + STATUT + LOGS
# =============================================================================

def run_daily_autopilot(
    db_path: Optional[str] = None,
    force: bool = False
) -> Dict[str, Any]:
    """
    Lance une analyse complète des partenaires puis publie
    jusqu'à DAILY_GAME_LIMIT jeux dans Supabase.

    Les images sont envoyées vers Cloudinary par publish_game().
    """

    now = datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    try:
        # -----------------------------------------------------------------
        # STATUT AUTOPILOT
        # -----------------------------------------------------------------

        cursor.execute("""
            SELECT value
            FROM autopilot_settings
            WHERE key = 'is_enabled'
        """)

        row_enabled = cursor.fetchone()

        is_enabled = (
            str(row_enabled["value"]) == "1"
            if row_enabled
            else True
        )

        if not is_enabled and not force:

            return {
                "success": False,
                "status": "disabled",
                "message": "🤖 AutoPilot est actuellement désactivé.",
                "games_published": 0,
                "today_total": get_today_published_count(db_path),
                "daily_limit": DAILY_GAME_LIMIT
            }

        # -----------------------------------------------------------------
        # LIMITE QUOTIDIENNE
        # -----------------------------------------------------------------

        published_today = get_today_published_count(db_path)

        remaining_slots = max(
            0,
            DAILY_GAME_LIMIT - published_today
        )

        if remaining_slots == 0 and not force:

            return {
                "success": True,
                "status": "limit_reached",
                "message": (
                    f"✅ Limite journalière atteinte "
                    f"({DAILY_GAME_LIMIT}/{DAILY_GAME_LIMIT})."
                ),
                "games_published": 0,
                "today_total": published_today,
                "daily_limit": DAILY_GAME_LIMIT
            }

        # -----------------------------------------------------------------
        # PARTENAIRES ACTIFS
        # -----------------------------------------------------------------

        active_partners = get_active_partners(db_path)

        if not active_partners:

            return {
                "success": False,
                "status": "no_partners",
                "message": (
                    "⚠️ Aucun partenaire actif configuré."
                ),
                "games_published": 0,
                "today_total": published_today,
                "daily_limit": DAILY_GAME_LIMIT
            }

        # -----------------------------------------------------------------
        # VARIABLES D'ANALYSE
        # -----------------------------------------------------------------

        total_pages = 0
        total_detected = 0
        total_duplicates = 0
        total_invalid_links = 0

        all_candidates = []
        all_errors = []

        # -----------------------------------------------------------------
        # ANALYSE DES PARTENAIRES
        # -----------------------------------------------------------------

        for partner in active_partners:

            try:

                print(
                    f"[AutoPilot] Analyse : "
                    f"{partner.get('name')}"
                )

                scan_res = scan_partner_site(partner)

                total_pages += scan_res.get(
                    "pages_scanned",
                    0
                )

                total_detected += scan_res.get(
                    "games_detected",
                    0
                )

                total_duplicates += scan_res.get(
                    "duplicates",
                    0
                )

                total_invalid_links += scan_res.get(
                    "invalid_links",
                    0
                )

                all_candidates.extend(
                    scan_res.get(
                        "candidates",
                        []
                    )
                )

                all_errors.extend(
                    scan_res.get(
                        "errors",
                        []
                    )
                )

            except Exception as e:

                error_message = (
                    f"{partner.get('name', 'Partenaire')} : "
                    f"{str(e)[:200]}"
                )

                print(
                    f"[AutoPilot Scan Error] "
                    f"{error_message}"
                )

                all_errors.append(
                    error_message
                )

        # -----------------------------------------------------------------
        # SÉLECTION DES JEUX
        # -----------------------------------------------------------------

        published_games = []

        candidates_to_publish = (
            all_candidates[:remaining_slots]
        )

        for candidate in candidates_to_publish:

            try:

                # Vérification Supabase
                if game_exists_supabase(
                    candidate.get("title", ""),
                    candidate.get(
                        "external_url",
                        ""
                    )
                ):
                    total_duplicates += 1

                    print(
                        "[AutoPilot] Doublon Supabase : "
                        f"{candidate.get('title')}"
                    )

                    continue

                # Publication Supabase + Cloudinary
                success = publish_game(
                    candidate,
                    db_path
                )

                if success:

                    published_games.append(
                        candidate
                    )

                    print(
                        "[AutoPilot] Publication réussie : "
                        f"{candidate.get('title')}"
                    )

            except Exception as e:

                error_message = (
                    f"Publication "
                    f"{candidate.get('title', 'inconnu')} : "
                    f"{str(e)[:200]}"
                )

                print(
                    f"[AutoPilot Publish Error] "
                    f"{error_message}"
                )

                all_errors.append(
                    error_message
                )

        # -----------------------------------------------------------------
        # STATISTIQUES
        # -----------------------------------------------------------------

        new_published_count = len(
            published_games
        )

        new_today_total = (
            published_today +
            new_published_count
        )

        # -----------------------------------------------------------------
        # PROCHAINE EXÉCUTION
        # -----------------------------------------------------------------

        next_run_dt = (
            now + timedelta(days=1)
        ).replace(
            hour=10,
            minute=0,
            second=0,
            microsecond=0
        )

        next_run_str = next_run_dt.strftime(
            "%d/%m/%Y %H:%M"
        )

        # -----------------------------------------------------------------
        # STATUT
        # -----------------------------------------------------------------

        if new_published_count > 0:

            status_str = "SUCCESS"

        elif total_detected > 0:

            status_str = "NO_NEW_GAMES"

        else:

            status_str = "SCAN_EMPTY"

        # -----------------------------------------------------------------
        # SAUVEGARDE DU DERNIER RUN
        # -----------------------------------------------------------------

        cursor.execute("""
            UPDATE autopilot_settings
            SET value = ?
            WHERE key = 'last_run'
        """, (now_str,))

        cursor.execute("""
            UPDATE autopilot_settings
            SET value = ?
            WHERE key = 'next_run'
        """, (next_run_str,))

        # -----------------------------------------------------------------
        # LOG
        # -----------------------------------------------------------------

        details = json.dumps(
            {
                "errors": all_errors,
                "published_titles": [
                    game.get("title", "")
                    for game in published_games
                ],
                "candidates_count": len(
                    all_candidates
                ),
                "supabase": True,
                "cloudinary": True
            },
            ensure_ascii=False
        )

        cursor.execute("""
            INSERT INTO autopilot_logs (
                timestamp,
                partner_id,
                partner_name,
                pages_scanned,
                games_detected,
                duplicates_count,
                invalid_links_count,
                games_published_count,
                status,
                details_json
            )
            VALUES (
                ?,
                NULL,
                'Tous les partenaires',
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?
            )
        """, (
            now_str,
            total_pages,
            total_detected,
            total_duplicates,
            total_invalid_links,
            new_published_count,
            status_str,
            details
        ))

        conn.commit()

        # -----------------------------------------------------------------
        # MESSAGE FINAL
        # -----------------------------------------------------------------

        if new_published_count > 0:

            message = (
                f"✅ Analyse terminée. "
                f"{new_published_count} jeu(x) publié(s) "
                f"dans Supabase aujourd'hui "
                f"({new_today_total}/"
                f"{DAILY_GAME_LIMIT})."
            )

        elif total_detected > 0:

            message = (
                "🔎 Analyse terminée. "
                "Des jeux ont été détectés, "
                "mais aucun nouveau jeu n'a été publié."
            )

        else:

            message = (
                "🔎 Analyse terminée. "
                "Aucun nouveau jeu exploitable détecté."
            )

        return {
            "success": True,
            "status": status_str,
            "message": message,
            "games_published": new_published_count,
            "today_total": new_today_total,
            "daily_limit": DAILY_GAME_LIMIT,
            "pages_scanned": total_pages,
            "games_detected": total_detected,
            "duplicates": total_duplicates,
            "invalid_links": total_invalid_links,
            "errors": all_errors,
            "published_items": published_games,
            "timestamp": now_str,
            "next_run": next_run_str
        }

    except Exception as e:

        conn.rollback()

        print(
            f"[AutoPilot Fatal Error] {e}"
        )

        return {
            "success": False,
            "status": "ERROR",
            "message": (
                f"❌ Erreur AutoPilot : {str(e)}"
            ),
            "games_published": 0,
            "today_total": get_today_published_count(
                db_path
            ),
            "daily_limit": DAILY_GAME_LIMIT,
            "errors": [str(e)]
        }

    finally:

        conn.close()


# =============================================================================
# STATUT AUTOPILOT
# =============================================================================

def get_autopilot_status(
    db_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Retourne les données utilisées par admin_ai.html.
    """

    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # -----------------------------------------------------------------
    # ACTIVATION
    # -----------------------------------------------------------------

    cursor.execute("""
        SELECT value
        FROM autopilot_settings
        WHERE key = 'is_enabled'
    """)

    row_enabled = cursor.fetchone()

    is_enabled = (
        str(row_enabled["value"]) == "1"
        if row_enabled
        else True
    )

    status_label = (
        "active"
        if is_enabled
        else "inactive"
    )

    # -----------------------------------------------------------------
    # DERNIÈRE ANALYSE
    # -----------------------------------------------------------------

    cursor.execute("""
        SELECT value
        FROM autopilot_settings
        WHERE key = 'last_run'
    """)

    row_last = cursor.fetchone()

    raw_last = (
        row_last["value"]
        if row_last
        else ""
    )

    if raw_last:

        try:

            dt_last = datetime.strptime(
                raw_last,
                "%Y-%m-%d %H:%M:%S"
            )

            last_run = dt_last.strftime(
                "%d/%m/%Y %H:%M"
            )

        except Exception:

            last_run = raw_last

    else:

        last_run = "Aucune analyse récente"

    # -----------------------------------------------------------------
    # PROCHAINE ANALYSE
    # -----------------------------------------------------------------

    cursor.execute("""
        SELECT value
        FROM autopilot_settings
        WHERE key = 'next_run'
    """)

    row_next = cursor.fetchone()

    next_run = (
        row_next["value"]
        if row_next and row_next["value"]
        else "Demain à 10:00"
    )

    # -----------------------------------------------------------------
    # PARTENAIRES
    # -----------------------------------------------------------------

    cursor.execute("""
        SELECT *
        FROM autopilot_partners
        ORDER BY id DESC
    """)

    partners = [
        dict(row)
        for row in cursor.fetchall()
    ]

    # -----------------------------------------------------------------
    # LOGS
    # -----------------------------------------------------------------

    cursor.execute("""
        SELECT *
        FROM autopilot_logs
        ORDER BY id DESC
        LIMIT 20
    """)

    raw_logs = [
        dict(row)
        for row in cursor.fetchall()
    ]

    # -----------------------------------------------------------------
    # STATISTIQUES
    # -----------------------------------------------------------------

    cursor.execute("""
        SELECT
            COALESCE(
                SUM(pages_scanned), 0
            ) AS total_pages,

            COALESCE(
                SUM(games_detected), 0
            ) AS total_detected,

            COALESCE(
                SUM(duplicates_count), 0
            ) AS total_duplicates,

            COALESCE(
                SUM(invalid_links_count), 0
            ) AS total_invalid_links,

            COALESCE(
                SUM(games_published_count), 0
            ) AS total_published

        FROM autopilot_logs
    """)

    stat_row = cursor.fetchone()

    stats = {
        "pages_scanned": (
            stat_row["total_pages"]
            if stat_row
            else 0
        ),

        "games_detected": (
            stat_row["total_detected"]
            if stat_row
            else 0
        ),

        "duplicates": (
            stat_row["total_duplicates"]
            if stat_row
            else 0
        ),

        "invalid_links": (
            stat_row["total_invalid_links"]
            if stat_row
            else 0
        ),

        "games_published": (
            stat_row["total_published"]
            if stat_row
            else 0
        ),

        "errors": 0
    }

    # -----------------------------------------------------------------
    # JEUX PUBLIÉS AUJOURD'HUI
    # -----------------------------------------------------------------

    games_today = get_today_published_count(
        db_path
    )

    conn.close()

    return {
        "autopilot_status": status_label,
        "games_today": games_today,
        "daily_limit": DAILY_GAME_LIMIT,
        "partners": partners,
        "last_run": last_run,
        "next_run": next_run,
        "logs": raw_logs,
        "stats": stats
    }


# =============================================================================
# ACTIVATION / DÉSACTIVATION
# =============================================================================

def toggle_autopilot_status(
    enable: Optional[bool] = None,
    db_path: Optional[str] = None
) -> bool:
    """
    Active ou désactive l'AutoPilot.
    """

    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    try:

        if enable is None:

            cursor.execute("""
                SELECT value
                FROM autopilot_settings
                WHERE key = 'is_enabled'
            """)

            row = cursor.fetchone()

            current = (
                str(row["value"]) == "1"
                if row
                else True
            )

            new_val = (
                "0"
                if current
                else "1"
            )

        else:

            new_val = (
                "1"
                if enable
                else "0"
            )

        cursor.execute("""
            UPDATE autopilot_settings
            SET value = ?
            WHERE key = 'is_enabled'
        """, (new_val,))

        conn.commit()

        return new_val == "1"

    except Exception as e:

        conn.rollback()

        print(
            f"[AutoPilot Toggle Error] {e}"
        )

        return False

    finally:

        conn.close()


# =============================================================================
# TEST RAPIDE SUPABASE
# =============================================================================

def test_supabase_connection() -> Dict[str, Any]:
    """
    Teste les tables utilisées par NovaGaming.
    """

    result = {
        "success": False,
        "supabase": False,
        "tables": {},
        "error": None
    }

    try:

        supabase = get_supabase_client()

        result["supabase"] = True

        tables = [
            "jeux",
            "vues",
            "commentaires",
            "notifications"
        ]

        for table in tables:

            try:

                response = (
                    supabase
                    .table(table)
                    .select("*")
                    .limit(1)
                    .execute()
                )

                result["tables"][table] = {
                    "accessible": True,
                    "rows": len(
                        response.data or []
                    )
                }

            except Exception as e:

                result["tables"][table] = {
                    "accessible": False,
                    "error": str(e)
                }

        result["success"] = True

    except Exception as e:

        result["error"] = str(e)

    return result
