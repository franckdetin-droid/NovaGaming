"""
NovaGaming AutoPilot
====================
Module d'automatisation éthique, sécurisé et intelligent pour la détection
et la publication quotidienne de jeux partenaires sur NovaGaming (Maximum 2 jeux par jour).

Intégrations prises en charge :
- Supabase : Enregistrement et synchronisation dans la table 'jeux' distante
- Cloudinary : Upload automatique et sécurisé de la couverture et des images (image1 à image10)
- SQLite : Base locale NovaGaming existante (avec fallback transparent)

Structure de la table 'jeux' :
- id, nom, console, description, taille, version, langue, couverture,
  image1, image2, image3, image4, image5, image6, image7, image8, image9, image10,
  lien, telechargements, date_ajout
"""

import os
import re
import html
import sqlite3
import datetime
import urllib.parse
from typing import Dict, List, Optional, Tuple, Any

# Web scraping & parsing
try:
    import requests
except ImportError:
    requests = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

# Cloudinary
try:
    import cloudinary
    import cloudinary.uploader
    HAS_CLOUDINARY = True
except ImportError:
    cloudinary = None
    HAS_CLOUDINARY = False

# Supabase
try:
    from supabase import create_client, Client
    HAS_SUPABASE = True
except ImportError:
    create_client = None
    Client = None
    HAS_SUPABASE = False


# ==============================================================================
# CONFIGURATION GLOBALE ET VARIABLES D'ENVIRONNEMENT
# ==============================================================================

# Limite stricte de publication quotidienne
DAILY_GAME_LIMIT: int = 2

# Base de données locale SQLite (fallback / miroir)
DATABASE_PATH: str = os.getenv("NOVAGAMING_DB_PATH", os.path.join(os.getcwd(), "novagaming.db"))

# Configuration Supabase
SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", os.getenv("SUPABASE_ANON_KEY", os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")))

# Configuration Cloudinary
CLOUDINARY_CLOUD_NAME: str = os.getenv("CLOUDINARY_CLOUD_NAME", "")
CLOUDINARY_API_KEY: str = os.getenv("CLOUDINARY_API_KEY", "")
CLOUDINARY_API_SECRET: str = os.getenv("CLOUDINARY_API_SECRET", "")
CLOUDINARY_URL: str = os.getenv("CLOUDINARY_URL", "")

# Configuration HTTP
USER_AGENT: str = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 NovaGamingBot/1.0"
)
REQUEST_TIMEOUT: int = 12
MAX_PAGES_PER_PARTNER: int = 20

# Consoles et plateformes reconnues
KNOWN_CONSOLES: List[str] = [
    "PSP", "PS2", "PS1", "PS3", "PS4", "PS5", "PS Vita",
    "PC", "Android", "iOS",
    "Nintendo Switch", "Nintendo 3DS", "Nintendo DS", "GBA", "Game Boy Advance",
    "GameCube", "Wii", "Wii U", "N64", "Nintendo 64", "SNES", "NES",
    "Xbox", "Xbox 360", "Xbox One", "Xbox Series",
    "Mega Drive", "Dreamcast", "Arcade", "Neo Geo"
]

# Domaines publicitaires et de tracking à bannir strictement
AD_AND_TRACKING_DOMAINS: List[str] = [
    "doubleclick.net", "googleads.g.doubleclick.net", "googlesyndication.com",
    "adservice.google.com", "adsterra.com", "propellerads.com", "popads.net",
    "exoclick.com", "hilltopads.com", "monetag.com", "clks.pro", "shrinkme.io",
    "linkvertise.com", "adfly.com", "adf.ly", "ouo.io", "ouo.press", "shrinkearn.com",
    "shorte.st", "bc.vc", "admaven.com", "clicknupload.click", "infolinks.com",
    "mgid.com", "revcontent.com", "taboola.com", "outbrain.com", "trafficjunky.net"
]

# Extensions de fichiers de jeux valides
GAME_FILE_EXTENSIONS: List[str] = [
    ".iso", ".cso", ".zip", ".rar", ".7z", ".apk", ".xapk", ".exe", ".bin",
    ".cue", ".chd", ".pkg", ".vpk", ".nsp", ".xci", ".gba", ".nds", ".3ds",
    ".cia", ".wbfs", ".gcm", ".z64", ".n64", ".smc", ".sfc", ".nes", ".tar.gz"
]

# Serveurs de fichiers autorisés
AUTHORIZED_FILE_HOSTS: List[str] = [
    "drive.google.com", "mega.nz", "mediafire.com", "1fichier.com",
    "archive.org", "gofile.io", "pixeldrain.com", "github.com",
    "gitlab.com", "send.cm", "qiwi.gg", "uploadhaven.com", "download.novagaming.local"
]


# ==============================================================================
# INTÉGRATION CLOUDINARY
# ==============================================================================

_cloudinary_initialized = False

def init_cloudinary_if_needed() -> bool:
    """Initialise le client Cloudinary si les identifiants sont fournis."""
    global _cloudinary_initialized
    if _cloudinary_initialized:
        return True

    if not HAS_CLOUDINARY:
        return False

    if CLOUDINARY_URL:
        cloudinary.config(cloudinary_url=CLOUDINARY_URL)
        _cloudinary_initialized = True
        return True

    if CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET:
        cloudinary.config(
            cloud_name=CLOUDINARY_CLOUD_NAME,
            api_key=CLOUDINARY_API_KEY,
            api_secret=CLOUDINARY_API_SECRET,
            secure=True
        )
        _cloudinary_initialized = True
        return True

    return False


def upload_image_to_cloudinary(image_url: Optional[str], folder: str = "novagaming/games") -> Optional[str]:
    """
    Téléverse une image légitime vers Cloudinary et retourne l'URL sécurisée HTTPS.
    Si Cloudinary n'est pas configuré ou si l'upload échoue, retourne l'URL d'origine.
    """
    if not image_url or not isinstance(image_url, str):
        return None

    if not init_cloudinary_if_needed():
        return image_url

    try:
        response = cloudinary.uploader.upload(
            image_url,
            folder=folder,
            overwrite=True,
            resource_type="image"
        )
        secure_url = response.get("secure_url") or response.get("url")
        return secure_url if secure_url else image_url
    except Exception as e:
        print(f"[AutoPilot - Cloudinary] Erreur lors de l'upload de {image_url}: {e}")
        return image_url


# ==============================================================================
# INTÉGRATION SUPABASE
# ==============================================================================

_supabase_client: Optional[Any] = None

def get_supabase_client() -> Optional[Any]:
    """Retourne une instance du client Supabase si configuré."""
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client

    if not HAS_SUPABASE or not create_client:
        return None

    if SUPABASE_URL and SUPABASE_KEY:
        try:
            _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
            return _supabase_client
        except Exception as e:
            print(f"[AutoPilot - Supabase] Erreur d'initialisation : {e}")
            return None

    return None


def is_supabase_enabled() -> bool:
    """Indique si la connexion Supabase est active et fonctionnelle."""
    return get_supabase_client() is not None


# ==============================================================================
# GESTION DE LA BASE DE DONNÉES (SQLITE & TABLES AUTO-PILOT)
# ==============================================================================

def get_db_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Ouvre une connexion SQLite avec row_factory."""
    path = db_path or DATABASE_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_autopilot_db(db_path: Optional[str] = None) -> None:
    """
    Initialise les tables locales sans jamais écraser les données existantes.
    Garantit la présence de la table 'jeux' et des colonnes attendues.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jeux (
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
            date_ajout TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            jeu_id INTEGER,
            ip_address TEXT,
            date_vue TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS commentaires (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            jeu_id INTEGER,
            auteur TEXT,
            message TEXT,
            note INTEGER,
            date_commentaire TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titre TEXT,
            message TEXT,
            lu INTEGER DEFAULT 0,
            date_notif TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS autopilot_partners (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            url TEXT NOT NULL UNIQUE,
            domain TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_scanned_at TIMESTAMP,
            games_found_count INTEGER DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS autopilot_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS autopilot_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_date DATE NOT NULL,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            finished_at TIMESTAMP,
            pages_analyzed INTEGER DEFAULT 0,
            games_detected INTEGER DEFAULT 0,
            duplicates_count INTEGER DEFAULT 0,
            invalid_links_count INTEGER DEFAULT 0,
            games_published INTEGER DEFAULT 0,
            status TEXT DEFAULT 'SUCCESS',
            details TEXT
        )
    """)

    cursor.execute("""
        INSERT OR IGNORE INTO autopilot_settings (key, value)
        VALUES ('autopilot_enabled', '1')
    """)

    conn.commit()
    conn.close()


# ==============================================================================
# GESTION DES PARTENAIRES
# ==============================================================================

def normalize_domain(url: str) -> str:
    """Extrait et normalise le nom de domaine."""
    if not url:
        return ""
    if not (url.startswith("http://") or url.startswith("https://")):
        url = "https://" + url
    parsed = urllib.parse.urlparse(url)
    netloc = parsed.netloc.lower()
    if ":" in netloc:
        netloc = netloc.split(":")[0]
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc


def add_partner(name: str, url: str, is_active: bool = True, db_path: Optional[str] = None) -> Dict[str, Any]:
    """Ajoute un partenaire à la liste blanche."""
    init_autopilot_db(db_path)
    url_clean = url.strip()
    if not (url_clean.startswith("http://") or url_clean.startswith("https://")):
        url_clean = "https://" + url_clean

    domain = normalize_domain(url_clean)
    if not domain:
        return {"success": False, "message": "URL de partenaire invalide"}

    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO autopilot_partners (name, url, domain, is_active)
            VALUES (?, ?, ?, ?)
            """,
            (name.strip(), url_clean, domain, 1 if is_active else 0),
        )
        conn.commit()
        partner_id = cursor.lastrowid
        return {"success": True, "partner_id": partner_id, "message": f"Partenaire '{name}' ajouté avec succès"}
    except sqlite3.IntegrityError:
        return {"success": False, "message": "Ce partenaire ou cette URL existe déjà"}
    finally:
        conn.close()


def delete_partner(partner_id: int, db_path: Optional[str] = None) -> bool:
    """Supprime un partenaire de la liste blanche."""
    init_autopilot_db(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM autopilot_partners WHERE id = ?", (partner_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def toggle_partner(partner_id: int, is_active: Optional[bool] = None, db_path: Optional[str] = None) -> bool:
    """Active ou désactive un partenaire."""
    init_autopilot_db(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    if is_active is None:
        cursor.execute("UPDATE autopilot_partners SET is_active = 1 - is_active WHERE id = ?", (partner_id,))
    else:
        cursor.execute("UPDATE autopilot_partners SET is_active = ? WHERE id = ?", (1 if is_active else 0, partner_id))
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return updated


def get_partners(active_only: bool = False, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retourne la liste des partenaires."""
    init_autopilot_db(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    if active_only:
        cursor.execute("SELECT * FROM autopilot_partners WHERE is_active = 1 ORDER BY id DESC")
    else:
        cursor.execute("SELECT * FROM autopilot_partners ORDER BY id DESC")
    rows = cursor.fetchall()
    partners = [dict(row) for row in rows]
    conn.close()
    return partners


def get_allowed_domains(db_path: Optional[str] = None) -> List[str]:
    """Retourne la liste stricte des domaines autorisés."""
    active_partners = get_partners(active_only=True, db_path=db_path)
    domains = set()
    for p in active_partners:
        dom = p.get("domain") or normalize_domain(p.get("url", ""))
        if dom:
            domains.add(dom)
    return list(domains)


# ==============================================================================
# VALIDATION ET VÉRIFICATION DES LIENS ET DOMAINES
# ==============================================================================

def is_domain_allowed(url: str, allowed_domains: List[str]) -> bool:
    """Vérifie si l'URL est sur un domaine autorisé ou un hébergeur réputé."""
    if not url:
        return False
    domain = normalize_domain(url)
    if not domain:
        return False

    for allowed in allowed_domains:
        if domain == allowed or domain.endswith("." + allowed):
            return True

    for host in AUTHORIZED_FILE_HOSTS:
        if domain == host or domain.endswith("." + host):
            return True

    return False


def is_ad_or_tracker_url(url: str) -> bool:
    """Détecte les régies publicitaires et réducteurs trompeurs."""
    if not url:
        return True
    url_lower = url.lower()
    domain = normalize_domain(url)

    for ad_dom in AD_AND_TRACKING_DOMAINS:
        if ad_dom in domain or ad_dom in url_lower:
            return True

    if re.search(r"/(ads?|popunder|banner|tracker|affiliate|pixel|adclick|adserve)/", url_lower):
        return True

    return False


def validate_and_clean_link(url: str, allowed_domains: List[str], base_url: Optional[str] = None) -> Tuple[bool, Optional[str], Optional[str]]:
    """Valide, nettoie et résout une URL de téléchargement en conservant ses paramètres."""
    if not url or not isinstance(url, str):
        return False, None, "URL vide ou non textuelle"

    url_str = url.strip()

    if url_str.startswith(("#", "javascript:", "mailto:", "tel:", "data:", "about:")):
        return False, None, "Protocole non supporté ou lien vide"

    if base_url:
        url_str = urllib.parse.urljoin(base_url, url_str)

    if not (url_str.startswith("http://") or url_str.startswith("https://")):
        return False, None, "L'URL doit commencer par http:// ou https://"

    if is_ad_or_tracker_url(url_str):
        return False, None, "Lien publicitaire ou de tracking détecté"

    if not is_domain_allowed(url_str, allowed_domains):
        domain = normalize_domain(url_str)
        return False, None, f"Domaine non autorisé ({domain})"

    return True, url_str, None


def validate_and_check_link(url: str, allowed_domains: List[str], base_url: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    """Vérification réseau légère sans télécharger le fichier."""
    is_valid, clean_url, error_msg = validate_and_clean_link(url, allowed_domains, base_url)
    if not is_valid or not clean_url:
        return False, error_msg or "Lien non valide"

    if requests is None:
        return True, "Validé sans requête réseau (requests non installé)"

    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.head(clean_url, headers=headers, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        if response.status_code in (405, 501):
            response = requests.get(clean_url, headers=headers, timeout=REQUEST_TIMEOUT, stream=True, allow_redirects=True)
            response.close()

        final_url = response.url
        if is_ad_or_tracker_url(final_url):
            return False, "Redirection vers un domaine publicitaire"

        if not is_domain_allowed(final_url, allowed_domains):
            final_domain = normalize_domain(final_url)
            return False, f"Redirection vers un domaine tiers non autorisé ({final_domain})"

        if response.status_code in (401, 403):
            return False, f"Accès protégé ou authentification requise (HTTP {response.status_code})"

        if response.status_code >= 400:
            return False, f"Lien inaccessible (HTTP {response.status_code})"

        return True, "Lien valide et accessible"

    except Exception as e:
        return False, f"Échec de connexion au serveur : {str(e)}"


def test_partner(partner_id_or_url: Any, db_path: Optional[str] = None) -> Dict[str, Any]:
    """Teste la connectivité d'un partenaire."""
    target_url = None
    if isinstance(partner_id_or_url, int) or (isinstance(partner_id_or_url, str) and partner_id_or_url.isdigit()):
        partners = get_partners(db_path=db_path)
        for p in partners:
            if p["id"] == int(partner_id_or_url):
                target_url = p["url"]
                break
    elif isinstance(partner_id_or_url, str):
        target_url = partner_id_or_url

    if not target_url:
        return {"success": False, "message": "Partenaire introuvable"}

    if requests is None:
        return {"success": True, "status_code": 200, "message": "Mode autonome (requests non requis)"}

    try:
        headers = {"User-Agent": USER_AGENT}
        resp = requests.get(target_url, headers=headers, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            return {
                "success": False,
                "status_code": resp.status_code,
                "message": f"Réponse HTTP inattendue : {resp.status_code}",
            }

        title = "Sans titre"
        links_count = 0

        if BeautifulSoup:
            soup = BeautifulSoup(resp.text, "html.parser")
            title = soup.title.string.strip() if soup.title and soup.title.string else "Sans titre"
            links_count = len(soup.find_all("a", href=True))
        else:
            match = re.search(r"<title>(.*?)</title>", resp.text, re.IGNORECASE | re.DOTALL)
            if match:
                title = match.group(1).strip()
            links_count = len(re.findall(r'<a\s+[^>]*href=["\']', resp.text, re.IGNORECASE))

        return {
            "success": True,
            "status_code": resp.status_code,
            "title": title,
            "links_found": links_count,
            "message": f"Connexion réussie ({resp.status_code}) - {links_count} liens détectés",
        }
    except Exception as e:
        return {"success": False, "message": f"Échec du test : {str(e)}"}


# ==============================================================================
# ANTI-DOUBLON (SQLITE + SUPABASE)
# ==============================================================================

def normalize_title(title: str) -> str:
    """Normalise un titre pour comparaison."""
    if not title:
        return ""
    t = title.lower()
    t = re.sub(
        r"\b(game|jeu|gratuit|free|download|télécharger|telecharger|rom|iso|cso|apk|rip|repack|v\d+(\.\d+)*)\b",
        "",
        t,
    )
    t = re.sub(r"[^\w\s]", "", t)
    return " ".join(t.split())


def is_duplicate_game(
    nom: Optional[str] = None,
    console: Optional[str] = None,
    lien: Optional[str] = None,
    title: Optional[str] = None,
    platform: Optional[str] = None,
    db_path: Optional[str] = None,
    **kwargs
) -> bool:
    """
    Vérifie si le jeu existe déjà dans Supabase ou dans la base locale SQLite :
    - Comparaison par le lien direct de téléchargement
    - Comparaison par nom normalisé et console
    """
    game_name = nom or title
    game_console = console or platform
    game_link = lien

    if not game_name:
        return False

    norm_target = normalize_title(game_name)
    target_cons = (game_console or "").lower().strip()

    # 1. Vérification dans Supabase si actif
    sb = get_supabase_client()
    if sb:
        try:
            if game_link:
                res = sb.table("jeux").select("id").eq("lien", game_link).execute()
                if res.data and len(res.data) > 0:
                    return True

            res = sb.table("jeux").select("id, nom, console, lien").execute()
            if res.data:
                for g in res.data:
                    existing_nom = g.get("nom") or ""
                    existing_cons = (g.get("console") or "").lower().strip()
                    existing_link = g.get("lien") or ""

                    if normalize_title(existing_nom) == norm_target:
                        if not target_cons or not existing_cons or target_cons == existing_cons:
                            return True
                    if game_link and existing_link and game_link.strip() == existing_link.strip():
                        return True
        except Exception as e:
            print(f"[AutoPilot - Supabase Anti-Doublon] Info: {e}")

    # 2. Vérification locale SQLite
    init_autopilot_db(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    if game_link:
        cursor.execute("SELECT id FROM jeux WHERE lien = ?", (game_link,))
        if cursor.fetchone():
            conn.close()
            return True

    cursor.execute("SELECT id, nom, console, lien FROM jeux")
    existing_games = cursor.fetchall()
    conn.close()

    for g in existing_games:
        existing_nom = g["nom"] or ""
        existing_cons = (g["console"] or "").lower().strip()
        existing_link = g["lien"] or ""

        if normalize_title(existing_nom) == norm_target:
            if not target_cons or not existing_cons or target_cons == existing_cons:
                return True

        if game_link and existing_link and game_link.strip() == existing_link.strip():
            return True

    return False


# ==============================================================================
# DÉTECTION ET EXTRACTION DU JEU
# ==============================================================================

def clean_extracted_image_url(src: str, base_url: str) -> Optional[str]:
    """Valide et résout une URL d'image en URL absolue sans bannières publicitaires."""
    if not src or not isinstance(src, str):
        return None

    src = src.strip()
    if src.startswith("data:image/svg") or src.startswith("javascript:"):
        return None

    full_url = urllib.parse.urljoin(base_url, src)
    if not (full_url.startswith("http://") or full_url.startswith("https://")):
        return None

    url_lower = full_url.lower()

    ignored_patterns = [
        "banner", "ad-", "ads/", "advert", "sponsor", "tracker", "pixel",
        "1x1", "spacer", "logo", "favicon", "avatar", "badge", "footer",
        "header-bg", "button", "social", "facebook", "twitter", "instagram",
        "youtube", "discord", "telegram", "donate", "paypal", "captcha",
        "icon-", "star.png", "arrow.", "loader.", "spinner."
    ]
    for pattern in ignored_patterns:
        if pattern in url_lower:
            return None

    return full_url


def detect_console_from_text(text: str) -> Optional[str]:
    """Détecte la console depuis le texte."""
    if not text:
        return None
    for cons in KNOWN_CONSOLES:
        pattern = r"\b" + re.escape(cons) + r"\b"
        if re.search(pattern, text, re.IGNORECASE):
            return cons
    return None


def detect_file_size(text: str) -> Optional[str]:
    """Extrait la taille du fichier."""
    if not text:
        return None
    size_patterns = [
        r"(?:taille|size|file\s*size|poids)\s*[:=]?\s*(\d+(?:[.,]\d+)?\s*(?:Go|GB|Mo|MB|Ko|KB|G|M|K|octets|bytes))",
        r"\b(\d+(?:[.,]\d+)?\s*(?:Go|GB|Mo|MB))\b",
    ]
    for pattern in size_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def detect_version(text: str) -> Optional[str]:
    """Extrait la version du jeu."""
    if not text:
        return None
    version_patterns = [
        r"(?:version|ver\.?|build)\s*[:=]?\s*([vV]?\d+(?:\.\d+)+(?:[-_][a-zA-Z0-9]+)?)",
        r"\b(v\d+\.\d+(?:\.\d+)?)\b",
    ]
    for pattern in version_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            v_val = match.group(1).strip()
            if not v_val.lower().startswith("v") and v_val[0].isdigit():
                v_val = "v" + v_val
            return v_val
    return None


def detect_language(text: str) -> Optional[str]:
    """Extrait la langue du jeu."""
    if not text:
        return None
    lang_patterns = [
        r"(?:langue|language|langues|audio|texte)\s*[:=]?\s*([A-Za-z0-9\s/–-]+)",
    ]
    for pattern in lang_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            extracted = match.group(1).strip().split("\n")[0].split("<")[0].strip()
            if len(extracted) < 30:
                return extracted

    if re.search(r"\b(multi[- ]?5|multi[- ]?langues|multilangue)\b", text, re.IGNORECASE):
        return "Multi-langues"
    if re.search(r"\b(français|francais|vf|vostfr|french)\b", text, re.IGNORECASE):
        return "Français"
    if re.search(r"\b(english|anglais)\b", text, re.IGNORECASE):
        return "Anglais"

    return "Français / Multi"


def find_download_link_in_soup(soup, page_url: str, allowed_domains: List[str]) -> Optional[str]:
    """Recherche intelligente du lien de téléchargement direct."""
    download_keywords = [
        "télécharger", "telecharger", "download", "téléchargement",
        "direct download", "lien direct", "rom", "iso", "serveur 1", "server 1",
        "mirroir", "mirror", "télécharger le jeu", "get rom", "download now"
    ]

    candidates: List[Tuple[int, str]] = []

    for a in soup.find_all("a", href=True):
        raw_href = a["href"].strip()
        link_text = a.get_text().lower().strip()
        link_class = " ".join(a.get("class", [])).lower()
        link_id = (a.get("id") or "").lower()

        data_link = a.get("data-url") or a.get("data-href") or a.get("data-download") or a.get("data-link")
        target_href = data_link if data_link else raw_href

        is_valid, clean_url, _ = validate_and_clean_link(target_href, allowed_domains, page_url)
        if not is_valid or not clean_url:
            continue

        clean_lower = clean_url.lower()

        for ext in GAME_FILE_EXTENSIONS:
            if clean_lower.endswith(ext) or ext + "?" in clean_lower:
                candidates.append((100, clean_url))
                break

        for host in AUTHORIZED_FILE_HOSTS:
            if host in clean_lower:
                candidates.append((80, clean_url))
                break

        is_dl_button = any(kw in link_text or kw in link_class or kw in link_id for kw in download_keywords)
        if is_dl_button:
            if clean_url != page_url and not clean_url.rstrip("/") == page_url.rstrip("/"):
                candidates.append((60, clean_url))

    for elem in soup.find_all(["button", "div", "span"], attrs=True):
        data_link = elem.get("data-url") or elem.get("data-href") or elem.get("data-download") or elem.get("data-link")
        if data_link:
            is_valid, clean_url, _ = validate_and_clean_link(data_link, allowed_domains, page_url)
            if is_valid and clean_url:
                candidates.append((70, clean_url))

    if not candidates:
        return None

    candidates.sort(key=lambda c: c[0], reverse=True)
    return candidates[0][1]


def extract_game_from_page(html_content: str, page_url: str, allowed_domains: List[str]) -> Optional[Dict[str, Any]]:
    """Extrait l'ensemble des informations utiles du jeu."""
    if not html_content:
        return None

    title = None
    og_title = None
    h1_text = None
    soup = None

    if BeautifulSoup:
        soup = BeautifulSoup(html_content, "html.parser")
        og_tag = soup.find("meta", property="og:title")
        if og_tag and og_tag.get("content"):
            og_title = og_tag["content"].strip()

        h1_tag = soup.find("h1")
        if h1_tag and h1_tag.get_text().strip():
            h1_text = h1_tag.get_text().strip()

        if soup.title and soup.title.string:
            title = soup.title.string.strip()
    else:
        og_match = re.search(r'<meta\s+property=["\']og:title["\']\s+content=["\'](.*?)["\']', html_content, re.IGNORECASE)
        if og_match:
            og_title = html.unescape(og_match.group(1).strip())
        h1_match = re.search(r"<h1[^>]*>(.*?)</h1>", html_content, re.IGNORECASE | re.DOTALL)
        if h1_match:
            h1_text = html.unescape(re.sub(r"<[^>]+>", "", h1_match.group(1)).strip())
        title_match = re.search(r"<title>(.*?)</title>", html_content, re.IGNORECASE | re.DOTALL)
        if title_match:
            title = html.unescape(title_match.group(1).strip())

    title = og_title or h1_text or title
    if not title:
        return None

    title = re.split(r"[-|–—:]", title)[0].strip()
    title = re.sub(r"\s*\[(PSP|PS2|PS1|PC|Android|ROM|ISO)\]\s*", "", title, flags=re.IGNORECASE).strip()

    if len(title) < 2 or len(title) > 120:
        return None

    full_text = soup.get_text() if soup else re.sub(r"<[^>]+>", " ", html_content)

    console = detect_console_from_text(h1_text or "") or detect_console_from_text(title) or detect_console_from_text(full_text) or "PC"

    description = ""
    if soup:
        og_desc = soup.find("meta", property="og:description")
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if og_desc and og_desc.get("content"):
            description = og_desc["content"].strip()
        elif meta_desc and meta_desc.get("content"):
            description = meta_desc["content"].strip()
        else:
            for p in soup.find_all("p"):
                p_text = p.get_text().strip()
                if len(p_text) > 40 and not any(ign in p_text.lower() for ign in ["cookie", "politique", "copyright", "javascript"]):
                    description = p_text
                    break
    else:
        desc_match = re.search(r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']', html_content, re.IGNORECASE)
        if desc_match:
            description = html.unescape(desc_match.group(1).strip())

    if not description:
        description = f"Fiche complète et téléchargement du jeu {title} pour {console} sur NovaGaming."

    taille = detect_file_size(full_text) or "Inconnue"
    version = detect_version(full_text) or "v1.0"
    langue = detect_language(full_text) or "Français"

    couverture = None
    extra_images: List[str] = []

    if soup:
        og_img = soup.find("meta", property="og:image")
        if og_img and og_img.get("content"):
            couverture = clean_extracted_image_url(og_img["content"], page_url)

        for img in soup.find_all("img", src=True):
            img_src = img["src"]
            clean_img = clean_extracted_image_url(img_src, page_url)
            if clean_img:
                if not couverture:
                    couverture = clean_img
                elif clean_img != couverture and clean_img not in extra_images:
                    extra_images.append(clean_img)
                    if len(extra_images) >= 10:
                        break
    else:
        img_matches = re.findall(r'<img\s+[^>]*src=["\'](.*?)["\']', html_content, re.IGNORECASE)
        for src in img_matches:
            clean_img = clean_extracted_image_url(src, page_url)
            if clean_img:
                if not couverture:
                    couverture = clean_img
                elif clean_img != couverture and clean_img not in extra_images:
                    extra_images.append(clean_img)
                    if len(extra_images) >= 10:
                        break

    images_dict = {}
    for i in range(1, 11):
        images_dict[f"image{i}"] = extra_images[i - 1] if i <= len(extra_images) else None

    download_link = None
    if soup:
        download_link = find_download_link_in_soup(soup, page_url, allowed_domains)
    else:
        for a_match in re.finditer(r'<a\s+[^>]*href=["\'](.*?)["\'][^>]*>(.*?)</a>', html_content, re.IGNORECASE | re.DOTALL):
            href, txt = a_match.group(1), a_match.group(2)
            if any(kw in txt.lower() or kw in href.lower() for kw in ["download", "telecharger", "rom", "iso"]):
                is_val, cl_url, _ = validate_and_clean_link(href, allowed_domains, page_url)
                if is_val and cl_url:
                    download_link = cl_url
                    break

    return {
        "nom": title,
        "title": title,
        "console": console,
        "platform": console,
        "description": description[:600],
        "taille": taille,
        "version": version,
        "langue": langue,
        "couverture": couverture,
        "image_url": couverture,
        "image1": images_dict["image1"],
        "image2": images_dict["image2"],
        "image3": images_dict["image3"],
        "image4": images_dict["image4"],
        "image5": images_dict["image5"],
        "image6": images_dict["image6"],
        "image7": images_dict["image7"],
        "image8": images_dict["image8"],
        "image9": images_dict["image9"],
        "image10": images_dict["image10"],
        "lien": download_link,
        "external_url": download_link,
        "source_url": page_url,
    }


def analyze_partner(partner_id: int, db_path: Optional[str] = None) -> Dict[str, Any]:
    """Scanne les pages accessibles d'un partenaire."""
    init_autopilot_db(db_path)
    partners = get_partners(db_path=db_path)
    partner = next((p for p in partners if p["id"] == partner_id), None)
    if not partner:
        return {"success": False, "message": "Partenaire inexistant"}

    if not partner["is_active"]:
        return {"success": False, "message": "Partenaire inactif"}

    allowed_domains = get_allowed_domains(db_path=db_path)
    base_url = partner["url"]
    partner_domain = partner["domain"]

    if requests is None:
        return {"success": False, "message": "Module requests non installé"}

    headers = {"User-Agent": USER_AGENT}
    visited_pages = set()
    to_visit = [base_url]
    detected_games: List[Dict[str, Any]] = []

    pages_analyzed = 0

    while to_visit and pages_analyzed < MAX_PAGES_PER_PARTNER:
        current_url = to_visit.pop(0)
        if current_url in visited_pages:
            continue

        if not is_domain_allowed(current_url, [partner_domain]):
            continue

        visited_pages.add(current_url)
        pages_analyzed += 1

        try:
            resp = requests.get(current_url, headers=headers, timeout=REQUEST_TIMEOUT)
            if resp.status_code != 200:
                continue

            game_candidate = extract_game_from_page(resp.text, current_url, allowed_domains)
            if game_candidate and game_candidate.get("nom"):
                if not any(g["nom"] == game_candidate["nom"] for g in detected_games):
                    detected_games.append(game_candidate)

            if BeautifulSoup:
                soup = BeautifulSoup(resp.text, "html.parser")
                for a in soup.find_all("a", href=True):
                    full_link = urllib.parse.urljoin(current_url, a["href"])
                    if is_domain_allowed(full_link, [partner_domain]):
                        if not re.search(r"\.(png|jpg|jpeg|gif|svg|pdf|css|js|zip|iso|rar)$", full_link, re.IGNORECASE):
                            if full_link not in visited_pages and full_link not in to_visit:
                                to_visit.append(full_link)

        except Exception:
            continue

    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE autopilot_partners
        SET last_scanned_at = CURRENT_TIMESTAMP, games_found_count = games_found_count + ?
        WHERE id = ?
        """,
        (len(detected_games), partner_id),
    )
    conn.commit()
    conn.close()

    return {
        "success": True,
        "partner_name": partner["name"],
        "pages_analyzed": pages_analyzed,
        "games_detected": detected_games,
        "count": len(detected_games),
    }


# ==============================================================================
# COMPTEURS QUOTIDIENS ET PUBLICATION (SUPABASE & CLOUDINARY)
# ==============================================================================

def get_games_published_today(db_path: Optional[str] = None) -> int:
    """Retourne le nombre de jeux publiés aujourd'hui (Supabase ou SQLite)."""
    today_str = datetime.date.today().isoformat()

    sb = get_supabase_client()
    if sb:
        try:
            start_of_day = f"{today_str}T00:00:00"
            res = sb.table("jeux").select("id", count="exact").gte("date_ajout", start_of_day).execute()
            if res.count is not None:
                return res.count
        except Exception as e:
            print(f"[AutoPilot - Supabase Count] Info: {e}")

    init_autopilot_db(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT COUNT(*) as total FROM jeux
        WHERE DATE(date_ajout) = ?
        """,
        (today_str,),
    )
    row = cursor.fetchone()
    count = row["total"] if row else 0
    conn.close()
    return count


def is_autopilot_enabled(db_path: Optional[str] = None) -> bool:
    """Vérifie si l'AutoPilot est activé."""
    init_autopilot_db(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM autopilot_settings WHERE key = 'autopilot_enabled'")
    row = cursor.fetchone()
    conn.close()
    return row["value"] == "1" if row else True


def set_autopilot_enabled(enabled: bool, db_path: Optional[str] = None) -> None:
    """Active ou désactive l'AutoPilot."""
    init_autopilot_db(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO autopilot_settings (key, value, updated_at)
        VALUES ('autopilot_enabled', ?, CURRENT_TIMESTAMP)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
        """,
        ("1" if enabled else "0",),
    )
    conn.commit()
    conn.close()


def publish_game(game_data: Dict[str, Any], db_path: Optional[str] = None) -> bool:
    """
    Enregistre et publie un jeu validé :
    1. Téléverse la couverture et les images sur Cloudinary si configuré.
    2. Insère le jeu dans Supabase si configuré.
    3. Insère le jeu dans la base locale SQLite.
    """
    init_autopilot_db(db_path)

    game_name = game_data.get("nom") or game_data.get("title")
    if not game_name:
        return False

    download_link = game_data.get("lien") or game_data.get("external_url")
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 1. Traitement des images avec Cloudinary
    couverture = game_data.get("couverture") or game_data.get("image_url")
    if couverture:
        couverture = upload_image_to_cloudinary(couverture, folder="novagaming/covers")

    images_cloudinary = {}
    for i in range(1, 11):
        raw_img = game_data.get(f"image{i}")
        if raw_img:
            images_cloudinary[f"image{i}"] = upload_image_to_cloudinary(raw_img, folder="novagaming/screenshots")
        else:
            images_cloudinary[f"image{i}"] = None

    payload = {
        "nom": game_name,
        "console": game_data.get("console") or game_data.get("platform", "PC"),
        "description": game_data.get("description", ""),
        "taille": game_data.get("taille", "Inconnue"),
        "version": game_data.get("version", "v1.0"),
        "langue": game_data.get("langue", "Français"),
        "couverture": couverture,
        "image1": images_cloudinary["image1"],
        "image2": images_cloudinary["image2"],
        "image3": images_cloudinary["image3"],
        "image4": images_cloudinary["image4"],
        "image5": images_cloudinary["image5"],
        "image6": images_cloudinary["image6"],
        "image7": images_cloudinary["image7"],
        "image8": images_cloudinary["image8"],
        "image9": images_cloudinary["image9"],
        "image10": images_cloudinary["image10"],
        "lien": download_link,
        "telechargements": 0,
        "date_ajout": now_str,
    }

    # 2. Envoi vers Supabase si disponible
    sb = get_supabase_client()
    if sb:
        try:
            sb.table("jeux").insert(payload).execute()
        except Exception as e:
            print(f"[AutoPilot - Supabase Insert] Info: {e}")

    # 3. Envoi vers la base locale SQLite
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO jeux (
                nom, console, description, taille, version, langue, couverture,
                image1, image2, image3, image4, image5, image6, image7, image8, image9, image10,
                lien, telechargements, date_ajout
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
            """,
            (
                payload["nom"],
                payload["console"],
                payload["description"],
                payload["taille"],
                payload["version"],
                payload["langue"],
                payload["couverture"],
                payload["image1"],
                payload["image2"],
                payload["image3"],
                payload["image4"],
                payload["image5"],
                payload["image6"],
                payload["image7"],
                payload["image8"],
                payload["image9"],
                payload["image10"],
                payload["lien"],
                now_str,
            ),
        )
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"[AutoPilot - SQLite Insert] Erreur: {e}")
        return False
    finally:
        conn.close()


# ==============================================================================
# FONCTION PRINCIPALE (RUN DAILY AUTOPILOT)
# ==============================================================================

def run_daily_autopilot(db_path: Optional[str] = None) -> Dict[str, Any]:
    """Exécute le cycle complet de l'AutoPilot NovaGaming."""
    init_autopilot_db(db_path)
    today_date = datetime.date.today().isoformat()
    now_ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    published_today = get_games_published_today(db_path)
    remaining_slots = max(0, DAILY_GAME_LIMIT - published_today)

    report: Dict[str, Any] = {
        "status": "SUCCESS",
        "date": today_date,
        "started_at": now_ts,
        "is_enabled": is_autopilot_enabled(db_path),
        "games_already_published_today": published_today,
        "daily_limit": DAILY_GAME_LIMIT,
        "remaining_slots": remaining_slots,
        "pages_analyzed": 0,
        "games_detected": 0,
        "duplicates_count": 0,
        "invalid_links_count": 0,
        "games_published": 0,
        "published_items": [],
        "errors": [],
    }

    if not report["is_enabled"]:
        report["status"] = "SKIPPED"
        report["errors"].append("AutoPilot désactivé dans les paramètres.")
        _record_run(report, db_path)
        return report

    if remaining_slots <= 0:
        report["status"] = "SKIPPED"
        report["errors"].append(f"Limite quotidienne atteinte ({DAILY_GAME_LIMIT}/{DAILY_GAME_LIMIT} publiés aujourd'hui).")
        _record_run(report, db_path)
        return report

    active_partners = get_partners(active_only=True, db_path=db_path)
    if not active_partners:
        report["status"] = "NO_PARTNERS"
        report["errors"].append("Aucun partenaire actif configuré dans la liste blanche.")
        _record_run(report, db_path)
        return report

    allowed_domains = get_allowed_domains(db_path=db_path)

    all_candidates: List[Dict[str, Any]] = []
    for partner in active_partners:
        analysis = analyze_partner(partner["id"], db_path=db_path)
        if analysis.get("success"):
            report["pages_analyzed"] += analysis.get("pages_analyzed", 0)
            all_candidates.extend(analysis.get("games_detected", []))
        else:
            report["errors"].append(f"Partenaire '{partner['name']}': {analysis.get('message')}")

    report["games_detected"] = len(all_candidates)

    valid_candidates: List[Dict[str, Any]] = []

    for cand in all_candidates:
        if is_duplicate_game(
            nom=cand.get("nom"),
            console=cand.get("console"),
            lien=cand.get("lien"),
            db_path=db_path,
        ):
            report["duplicates_count"] += 1
            continue

        download_link = cand.get("lien")
        if not download_link:
            report["invalid_links_count"] += 1
            report["errors"].append(f"Aucun lien de téléchargement valide pour '{cand.get('nom')}'")
            continue

        is_valid, reason = validate_and_check_link(download_link, allowed_domains, cand.get("source_url"))
        if not is_valid:
            report["invalid_links_count"] += 1
            report["errors"].append(f"Lien rejeté pour '{cand.get('nom')}' : {reason}")
            continue

        valid_candidates.append(cand)

    to_publish = valid_candidates[:remaining_slots]

    for item in to_publish:
        success = publish_game(item, db_path=db_path)
        if success:
            report["games_published"] += 1
            report["published_items"].append({
                "nom": item["nom"],
                "console": item["console"],
                "taille": item["taille"],
                "version": item["version"],
                "langue": item["langue"],
                "lien": item["lien"],
            })
        else:
            report["errors"].append(f"Échec de l'insertion en base pour : {item['nom']}")

    report["finished_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _record_run(report, db_path)
    return report


def _record_run(report: Dict[str, Any], db_path: Optional[str] = None) -> None:
    """Enregistre le rapport d'exécution dans la table autopilot_runs."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    today_date = datetime.date.today().isoformat()
    details_str = "; ".join(report.get("errors", [])) if report.get("errors") else "Exécution terminée avec succès."
    cursor.execute(
        """
        INSERT INTO autopilot_runs (
            run_date, started_at, finished_at, pages_analyzed,
            games_detected, duplicates_count, invalid_links_count,
            games_published, status, details
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            today_date,
            report.get("started_at"),
            report.get("finished_at") or report.get("started_at"),
            report.get("pages_analyzed", 0),
            report.get("games_detected", 0),
            report.get("duplicates_count", 0),
            report.get("invalid_links_count", 0),
            report.get("games_published", 0),
            report.get("status", "SUCCESS"),
            details_str[:500],
        ),
    )
    conn.commit()
    conn.close()


# ==============================================================================
# FONCTIONS DE LECTURE POUR FLASK / ADMIN_AI.HTML
# ==============================================================================

def get_autopilot_history(limit: int = 10, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retourne l'historique des exécutions."""
    init_autopilot_db(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM autopilot_runs ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    history = [dict(row) for row in rows]
    conn.close()
    return history


def get_autopilot_stats(db_path: Optional[str] = None) -> Dict[str, Any]:
    """Retourne les métriques globales."""
    init_autopilot_db(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            COALESCE(SUM(pages_analyzed), 0) as total_pages,
            COALESCE(SUM(games_detected), 0) as total_detected,
            COALESCE(SUM(duplicates_count), 0) as total_duplicates,
            COALESCE(SUM(invalid_links_count), 0) as total_invalid,
            COALESCE(SUM(games_published), 0) as total_published
        FROM autopilot_runs
    """)
    totals = dict(cursor.fetchone() or {})

    cursor.execute("SELECT started_at FROM autopilot_runs ORDER BY id DESC LIMIT 1")
    last_row = cursor.fetchone()
    last_run = last_row["started_at"] if last_row else "Jamais"

    conn.close()

    return {
        "pages_analyzed": totals.get("total_pages", 0),
        "games_detected": totals.get("total_detected", 0),
        "duplicates": totals.get("total_duplicates", 0),
        "invalid_links": totals.get("total_invalid", 0),
        "games_published": totals.get("total_published", 0),
        "last_run": last_run,
    }


def get_admin_dashboard_data(db_path: Optional[str] = None) -> Dict[str, Any]:
    """Rassemble toutes les variables attendues par templates/admin_ai.html."""
    init_autopilot_db(db_path)
    is_active = is_autopilot_enabled(db_path)
    games_today = get_games_published_today(db_path)
    partners = get_partners(db_path=db_path)
    history = get_autopilot_history(limit=10, db_path=db_path)
    stats = get_autopilot_stats(db_path=db_path)

    next_run = "Demain 10:00"
    if stats.get("last_run") and stats["last_run"] != "Jamais":
        try:
            dt = datetime.datetime.strptime(stats["last_run"], "%Y-%m-%d %H:%M:%S")
            next_dt = dt + datetime.timedelta(days=1)
            next_run = next_dt.strftime("%d/%m/%Y %H:%M")
        except Exception:
            next_run = "Demain 10:00"

    return {
        "autopilot_status": {
            "is_enabled": is_active,
            "label": "ACTIF" if is_active else "INACTIF",
            "color": "green" if is_active else "red",
        },
        "games_today": games_today,
        "daily_limit": DAILY_GAME_LIMIT,
        "partners": partners,
        "last_run": stats.get("last_run", "22/08/2026 10:00"),
        "next_run": next_run,
        "logs": history,
        "stats": stats,
    }
  def get_autopilot_status(db_path: Optional[str] = None) -> Dict[str, Any]:
    """Retourne les informations utilisées par la page admin_ai.html."""
    try:
        init_autopilot_db(db_path)

        stats = get_autopilot_stats(db_path)
        history = get_autopilot_history(limit=10, db_path=db_path)
        games_today = get_games_published_today(db_path)
        partners = get_partners(db_path=db_path)
        enabled = is_autopilot_enabled(db_path)

        last_run = stats.get("last_run", "Jamais")

        return {
            "success": True,
            "autopilot_status": "active" if enabled else "inactive",
            "games_today": games_today,
            "daily_limit": 2,
            "partners": partners,
            "last_run": last_run,
            "next_run": "Demain 10:00",
            "logs": history,
            "stats": stats
        }

    except Exception as e:
        return {
            "success": False,
            "autopilot_status": "error",
            "games_today": 0,
            "daily_limit": 2,
            "partners": [],
            "last_run": "Jamais",
            "next_run": "",
            "logs": [],
            "stats": {},
            "message": str(e)[:200]
          }


if __name__ == "__main__":
    print("NovaGaming AutoPilot - Initialisation et vérification...")
    init_autopilot_db()
    print(f"Supabase connecté : {'Oui' if is_supabase_enabled() else 'Non (mode SQLite)'}")
    print(f"Cloudinary configuré : {'Oui' if init_cloudinary_if_needed() else 'Non (URLs directes)'}")
    print(f"Limite quotidienne : {DAILY_GAME_LIMIT} jeux max")
    print(f"Statut AutoPilot : {'Activé' if is_autopilot_enabled() else 'Désactivé'}")
    print(f"Jeux publiés aujourd'hui : {get_games_published_today()}/{DAILY_GAME_LIMIT}")
