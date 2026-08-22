"""
=============================================================================
NovaGaming AutoPilot - Module d'automatisation et de publication intelligente
Version Améliorée avec Support Cloudinary Intégré
=============================================================================
Description :
    Module autonome pour NovaGaming permettant d'analyser les sites partenaires
    autorisés, de détecter les nouvelles fiches de jeux, d'héberger les jaquettes
    sur Cloudinary (avec repli automatique), de valider les liens externes et
    de publier automatiquement un maximum de 2 jeux par jour.

Fonctionnalités avancées :
    - Limite infranchissable : DAILY_GAME_LIMIT = 2 jeux / jour.
    - Support Cloudinary complet (SDK officiel ou API REST native via requests).
    - Système d'analyse adaptatif multicritère (JSON-LD, OpenGraph, Balises HTML).
    - Whitelist stricte des domaines partenaires & validation des redirections.
    - Anti-doublons rigoureux (titre normalisé, slug, URLs source et externe).
    - Préservation totale des tables existantes (CREATE TABLE IF NOT EXISTS).
    - Zéro clic artificiel, respect des protections techniques & CAPTCHA.
=============================================================================
"""

import os
import re
import json
import sqlite3
import unicodedata
import urllib.parse
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional, Tuple

import requests
from bs4 import BeautifulSoup

# =============================================================================
# CONFIGURATION GLOBALE
# =============================================================================

DAILY_GAME_LIMIT = 2
DEFAULT_DB_PATH = os.environ.get("NOVAGAMING_DB_PATH", "novagaming.db")
DEFAULT_TIMEOUT = 12  # secondes
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 NovaGamingBot/2.0"

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
}

# =============================================================================
# GESTION DU STOCKAGE CLOUDINARY (Images)
# =============================================================================

def get_cloudinary_config(db_path: Optional[str] = None) -> Dict[str, str]:
    """
    Récupère les identifiants Cloudinary depuis les variables d'environnement
    ou depuis la table `autopilot_settings`.
    """
    config = {
        "cloud_name": os.environ.get("CLOUDINARY_CLOUD_NAME", ""),
        "api_key": os.environ.get("CLOUDINARY_API_KEY", ""),
        "api_secret": os.environ.get("CLOUDINARY_API_SECRET", ""),
        "cloudinary_url": os.environ.get("CLOUDINARY_URL", "")
    }

    # Si CLOUDINARY_URL est défini (ex: cloudinary://api_key:api_secret@cloud_name)
    if config["cloudinary_url"] and not config["cloud_name"]:
        try:
            parsed = urllib.parse.urlparse(config["cloudinary_url"])
            config["cloud_name"] = parsed.hostname or ""
            config["api_key"] = parsed.username or ""
            config["api_secret"] = parsed.password or ""
        except Exception:
            pass

    # Vérification en base de données si manquant dans l'environnement
    if not config["cloud_name"]:
        try:
            conn = sqlite3.connect(db_path or DEFAULT_DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM autopilot_settings WHERE key LIKE 'cloudinary_%'")
            for row in cursor.fetchall():
                k, v = row[0], row[1]
                if k == "cloudinary_cloud_name":
                    config["cloud_name"] = v
                elif k == "cloudinary_api_key":
                    config["api_key"] = v
                elif k == "cloudinary_api_secret":
                    config["api_secret"] = v
            conn.close()
        except Exception:
            pass

    return config


def upload_image_to_cloudinary(image_url: str, slug: str, db_path: Optional[str] = None) -> str:
    """
    Téléverse de façon sécurisée l'image de couverture vers Cloudinary.
    - Utilise en priorité le SDK `cloudinary` si installé.
    - Utilise l'API REST Cloudinary avec `requests` en alternative.
    - Si Cloudinary n'est pas configuré ou en cas d'erreur, conserve l'URL d'origine.
    """
    if not image_url or not image_url.startswith(("http://", "https://")):
        return image_url

    cld_cfg = get_cloudinary_config(db_path)
    if not cld_cfg["cloud_name"]:
        # Cloudinary non configuré : renvoie l'URL originale directement
        return image_url

    # 1. Tentative via le SDK Cloudinary officiel (si présent)
    try:
        import cloudinary
        import cloudinary.uploader

        cloudinary.config(
            cloud_name=cld_cfg["cloud_name"],
            api_key=cld_cfg["api_key"],
            api_secret=cld_cfg["api_secret"],
            secure=True
        )

        res = cloudinary.uploader.upload(
            image_url,
            folder="novagaming/autopilot",
            public_id=f"game_{slug[:40]}",
            overwrite=True,
            resource_type="image",
            transformation=[
                {"width": 800, "height": 450, "crop": "limit"},
                {"quality": "auto", "fetch_format": "auto"}
            ]
        )
        if res and "secure_url" in res:
            return res["secure_url"]
    except ImportError:
        pass
    except Exception as e:
        print(f"[Cloudinary SDK Upload Warning] {e}")

    # 2. Tentative via l'API REST native Cloudinary (sans dépendance externe lourde)
    try:
        if cld_cfg["cloud_name"] and cld_cfg["api_key"] and cld_cfg["api_secret"]:
            import time
            import hashlib

            timestamp = int(time.time())
            folder = "novagaming/autopilot"
            public_id = f"game_{slug[:40]}"

            # Génération de la signature Cloudinary
            sig_params = f"folder={folder}&overwrite=true&public_id={public_id}&timestamp={timestamp}{cld_cfg['api_secret']}"
            signature = hashlib.sha1(sig_params.encode("utf-8")).hexdigest()

            upload_endpoint = f"https://api.cloudinary.com/v1_1/{cld_cfg['cloud_name']}/image/upload"
            payload = {
                "file": image_url,
                "api_key": cld_cfg["api_key"],
                "timestamp": timestamp,
                "folder": folder,
                "public_id": public_id,
                "overwrite": "true",
                "signature": signature
            }

            resp = requests.post(upload_endpoint, data=payload, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                if "secure_url" in data:
                    return data["secure_url"]
    except Exception as e:
        print(f"[Cloudinary REST Upload Warning] {e}")

    # Repli sûr sur l'URL distante légale
    return image_url


# =============================================================================
# GESTION ET CONNEXION À LA BASE DE DONNÉES
# =============================================================================

def get_db_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Établit une connexion sécurisée à la base SQLite existante de NovaGaming."""
    path = db_path or DEFAULT_DB_PATH
    conn = sqlite3.connect(path, timeout=15)
    conn.row_factory = sqlite3.Row
    return conn


def init_autopilot_db(db_path: Optional[str] = None) -> None:
    """
    Initialise UNIQUEMENT les tables propres à AutoPilot avec CREATE TABLE IF NOT EXISTS.
    Ne supprime ni ne réinitialise jamais aucune donnée existante.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    try:
        # Table des sites partenaires autorisés
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

        # Table d'historique des exécutions et rapports AutoPilot
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
                details_json TEXT,
                FOREIGN KEY (partner_id) REFERENCES autopilot_partners (id) ON DELETE SET NULL
            )
        """)

        # Table de suivi des jeux publiés par l'AutoPilot (anti-doublon historique)
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
                partner_id INTEGER,
                FOREIGN KEY (partner_id) REFERENCES autopilot_partners (id) ON DELETE SET NULL
            )
        """)

        # Table des paramètres globaux de l'AutoPilot
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS autopilot_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        # Paramètres par défaut
        cursor.execute("INSERT OR IGNORE INTO autopilot_settings (key, value) VALUES ('is_enabled', '1')")
        cursor.execute("INSERT OR IGNORE INTO autopilot_settings (key, value) VALUES ('daily_limit', ?)", (str(DAILY_GAME_LIMIT),))
        cursor.execute("INSERT OR IGNORE INTO autopilot_settings (key, value) VALUES ('last_run', '')")
        cursor.execute("INSERT OR IGNORE INTO autopilot_settings (key, value) VALUES ('next_run', '')")
        cursor.execute("INSERT OR IGNORE INTO autopilot_settings (key, value) VALUES ('cloudinary_cloud_name', '')")
        cursor.execute("INSERT OR IGNORE INTO autopilot_settings (key, value) VALUES ('cloudinary_api_key', '')")
        cursor.execute("INSERT OR IGNORE INTO autopilot_settings (key, value) VALUES ('cloudinary_api_secret', '')")

        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[AutoPilot DB Init Error] {e}")
    finally:
        conn.close()


try:
    init_autopilot_db()
except Exception:
    pass


# =============================================================================
# UTILITAIRES & NORMALISATION
# =============================================================================

def normalize_text(text: Optional[str]) -> str:
    """Normalise un texte pour comparaison stricte (sans accents, minuscules, sans ponctuation)."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text).encode("ASCII", "ignore").decode("utf-8")
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", " ", text).strip()
    return text


def generate_slug(text: str) -> str:
    """Génère un slug URL propre et compatible SEO."""
    norm = normalize_text(text)
    slug = re.sub(r"\s+", "-", norm)
    return slug[:120] if slug else "jeu-inconnu"


def extract_domain(url: str) -> str:
    """Extrait le nom de domaine principal (sans www ni port)."""
    try:
        parsed = urllib.parse.urlparse(url)
        netloc = parsed.netloc.lower()
        if ":" in netloc:
            netloc = netloc.split(":")[0]
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc
    except Exception:
        return ""


def is_domain_allowed(url: str, allowed_domains: List[str]) -> bool:
    """Vérifie si le domaine de l'URL appartient à la whitelist des domaines autorisés."""
    url_domain = extract_domain(url)
    if not url_domain:
        return False
    for allowed in allowed_domains:
        clean = allowed.strip().lower()
        if clean.startswith("www."):
            clean = clean[4:]
        if url_domain == clean or url_domain.endswith("." + clean):
            return True
    return False


# =============================================================================
# GESTION DES PARTENAIRES
# =============================================================================

def get_all_partners(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Récupère tous les partenaires enregistrés."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM autopilot_partners ORDER BY id DESC")
    rows = cursor.fetchall()
    partners = [dict(row) for row in rows]
    conn.close()
    return partners


def get_active_partners(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Récupère uniquement les partenaires actuellement activés."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM autopilot_partners WHERE is_active = 1 ORDER BY id ASC")
    rows = cursor.fetchall()
    partners = [dict(row) for row in rows]
    conn.close()
    return partners


def add_partner(name: str, base_url: str, allowed_domains: Optional[str] = None, db_path: Optional[str] = None) -> Tuple[bool, str]:
    """Ajoute un nouveau partenaire à la liste blanche."""
    clean_name = name.strip()
    clean_url = base_url.strip()
    if not clean_url.startswith(("http://", "https://")):
        clean_url = "https://" + clean_url

    domain = extract_domain(clean_url)
    if not domain:
        return False, "URL de partenaire invalide."

    domains_list = [domain]
    if allowed_domains:
        for d in allowed_domains.split(","):
            d_clean = extract_domain(d.strip()) or d.strip().lower()
            if d_clean and d_clean not in domains_list:
                domains_list.append(d_clean)
    allowed_domains_str = ",".join(domains_list)

    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            INSERT INTO autopilot_partners (name, base_url, allowed_domains, is_active, created_at)
            VALUES (?, ?, ?, 1, ?)
        """, (clean_name or domain, clean_url, allowed_domains_str, now))
        conn.commit()
        return True, "Partenaire ajouté avec succès."
    except sqlite3.IntegrityError:
        return False, "Ce partenaire ou cette URL existe déjà."
    except Exception as e:
        return False, f"Erreur lors de l'ajout : {str(e)}"
    finally:
        conn.close()


def delete_partner(partner_id: int, db_path: Optional[str] = None) -> Tuple[bool, str]:
    """Supprime un partenaire."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM autopilot_partners WHERE id = ?", (partner_id,))
        conn.commit()
        return True, "Partenaire supprimé."
    except Exception as e:
        return False, f"Erreur lors de la suppression : {str(e)}"
    finally:
        conn.close()


def toggle_partner(partner_id: int, db_path: Optional[str] = None) -> Tuple[bool, str]:
    """Bascule le statut d'un partenaire (Actif / Inactif)."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT is_active FROM autopilot_partners WHERE id = ?", (partner_id,))
        row = cursor.fetchone()
        if not row:
            return False, "Partenaire introuvable."
        new_status = 0 if row["is_active"] == 1 else 1
        cursor.execute("UPDATE autopilot_partners SET is_active = ? WHERE id = ?", (new_status, partner_id))
        conn.commit()
        msg = "Partenaire activé." if new_status == 1 else "Partenaire désactivé."
        return True, msg
    except Exception as e:
        return False, f"Erreur : {str(e)}"
    finally:
        conn.close()


def test_partner(partner_id: int, db_path: Optional[str] = None) -> Dict[str, Any]:
    """Vérifie la disponibilité et la conformité d'un partenaire."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM autopilot_partners WHERE id = ?", (partner_id,))
    partner = cursor.fetchone()
    conn.close()

    if not partner:
        return {"success": False, "message": "Partenaire introuvable."}

    url = partner["base_url"]
    try:
        response = requests.get(url, headers=HEADERS, timeout=DEFAULT_TIMEOUT, allow_redirects=True)
        if response.status_code in (401, 403):
            return {
                "success": False,
                "status_code": response.status_code,
                "message": "Accès refusé par le partenaire (401/403)."
            }
        
        html_lower = response.text.lower()
        if "captcha" in html_lower or ("cloudflare" in html_lower and "challenge" in html_lower):
            return {
                "success": False,
                "status_code": response.status_code,
                "message": "Protection technique ou CAPTCHA détecté."
            }

        return {
            "success": True,
            "status_code": response.status_code,
            "response_time_ms": int(response.elapsed.total_seconds() * 1000),
            "final_url": response.url,
            "message": "Partenaire accessible et opérationnel."
        }
    except requests.exceptions.Timeout:
        return {"success": False, "message": "Délai d'attente dépassé (Timeout)."}
    except requests.exceptions.RequestException as e:
        return {"success": False, "message": f"Erreur de connexion : {str(e)}"}


# =============================================================================
# VALIDATION DES LIENS & ANTI-DOUBLON
# =============================================================================

def get_today_published_count(db_path: Optional[str] = None) -> int:
    """Retourne le nombre exact de jeux publiés aujourd'hui."""
    today_str = date.today().isoformat()
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) AS total FROM autopilot_published WHERE published_date = ?", (today_str,))
    row = cursor.fetchone()
    count = row["total"] if row else 0
    conn.close()
    return count


def is_game_duplicate(game: Dict[str, Any], db_path: Optional[str] = None) -> bool:
    """
    Vérification anti-doublon multicritère :
    - Titre normalisé
    - Slug
    - URL source de la fiche
    - Lien externe
    """
    norm_title = normalize_text(game.get("title", ""))
    slug = game.get("slug", "")
    source_url = game.get("source_url", "").strip()
    external_url = game.get("external_url", "").strip()

    if not norm_title:
        return True

    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # 1. Vérification dans autopilot_published
    cursor.execute("""
        SELECT id FROM autopilot_published
        WHERE normalized_title = ? OR slug = ? OR source_url = ? OR external_url = ?
        LIMIT 1
    """, (norm_title, slug, source_url, external_url))
    if cursor.fetchone():
        conn.close()
        return True

    # 2. Vérification dans la table de jeux existante (games / jeux)
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('games', 'jeux')")
        table_row = cursor.fetchone()
        if table_row:
            table_name = table_row[0]
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [col[1].lower() for col in cursor.fetchall()]

            query_parts = []
            params = []

            if "slug" in columns and slug:
                query_parts.append("slug = ?")
                params.append(slug)
            if "title" in columns:
                query_parts.append("LOWER(title) = ?")
                params.append(game.get("title", "").strip().lower())
            elif "name" in columns:
                query_parts.append("LOWER(name) = ?")
                params.append(game.get("title", "").strip().lower())
            elif "nom" in columns:
                query_parts.append("LOWER(nom) = ?")
                params.append(game.get("title", "").strip().lower())

            if "source_url" in columns and source_url:
                query_parts.append("source_url = ?")
                params.append(source_url)
            if "download_url" in columns and external_url:
                query_parts.append("download_url = ?")
                params.append(external_url)
            elif "external_url" in columns and external_url:
                query_parts.append("external_url = ?")
                params.append(external_url)

            if query_parts:
                sql = f"SELECT id FROM {table_name} WHERE " + " OR ".join(query_parts) + " LIMIT 1"
                cursor.execute(sql, tuple(params))
                if cursor.fetchone():
                    conn.close()
                    return True
    except Exception:
        pass

    conn.close()
    return False


def validate_external_link(url: str, allowed_domains: List[str]) -> Tuple[bool, str]:
    """
    Valide l'URL externe :
    - Domaine vérifié contre la liste blanche.
    - Test HTTP sans téléchargement de contenu volumineux.
    - Rejet des redirections hors domaine autorisé.
    """
    if not url or not url.startswith(("http://", "https://")):
        return False, "URL invalide"

    if not is_domain_allowed(url, allowed_domains):
        return False, f"Domaine non autorisé ({extract_domain(url)})"

    try:
        resp = requests.head(url, headers=HEADERS, timeout=8, allow_redirects=True)
        if resp.status_code == 405:  # Méthode HEAD non autorisée par le serveur
            resp = requests.get(url, headers=HEADERS, timeout=8, allow_redirects=True, stream=True)
            resp.close()

        if resp.status_code not in (200, 301, 302, 307, 308):
            return False, f"Code HTTP : {resp.status_code}"

        final_domain = extract_domain(resp.url)
        if not is_domain_allowed(resp.url, allowed_domains):
            return False, f"Redirection externe non autorisée ({final_domain})"

        return True, "Valide"
    except requests.exceptions.Timeout:
        return False, "Timeout lors de la vérification"
    except requests.exceptions.RequestException as e:
        return False, f"Erreur réseau : {str(e)[:50]}"


# =============================================================================
# ANALYSE & DÉTECTION DES FICHES DE JEUX
# =============================================================================

def parse_game_card(soup_element, base_url: str, allowed_domains: List[str]) -> Optional[Dict[str, Any]]:
    """
    Extrait les données structurées d'une fiche de jeu HTML :
    - Titre, description, plateforme, catégorie, jaquette et liens.
    """
    try:
        # 1. Extraction du Titre
        title_el = (
            soup_element.find(["h1", "h2", "h3", "h4"])
            or soup_element.find(class_=re.compile(r"(title|titre|game-name|name)", re.I))
        )
        title = title_el.get_text(strip=True) if title_el else ""
        if not title or len(title) < 2:
            return None

        # 2. Extraction de la Description
        desc_el = (
            soup_element.find(class_=re.compile(r"(desc|description|excerpt|summary|info|details|story)", re.I))
            or soup_element.find("p")
        )
        description = desc_el.get_text(strip=True) if desc_el else f"Découvrez {title} sur NovaGaming. Fiche officielle et liens partenaires."

        # 3. Extraction de la Plateforme
        plat_el = soup_element.find(class_=re.compile(r"(platform|plateforme|system|os|support)", re.I))
        platform_text = plat_el.get_text(strip=True) if plat_el else ""
        
        # Détection intelligente de plateforme
        detected_platform = "PC"
        full_text_search = f"{title} {platform_text} {soup_element.get_text()}".lower()
        if "switch" in full_text_search:
            detected_platform = "Nintendo Switch"
        elif "ps5" in full_text_search or "playstation 5" in full_text_search:
            detected_platform = "PS5"
        elif "ps4" in full_text_search or "playstation 4" in full_text_search:
            detected_platform = "PS4"
        elif "xbox" in full_text_search:
            detected_platform = "Xbox"
        elif "android" in full_text_search:
            detected_platform = "Android"

        # 4. Extraction de la Catégorie / Genre
        cat_el = soup_element.find(class_=re.compile(r"(category|categorie|genre|tag|type)", re.I))
        category = cat_el.get_text(strip=True) if cat_el else "Action"
        if not category:
            category = "Action"

        # 5. Extraction de la Jaquette / Image
        img_el = soup_element.find("img")
        raw_img_url = ""
        if img_el:
            raw_img = img_el.get("src") or img_el.get("data-src") or img_el.get("data-lazy-src") or ""
            if raw_img:
                raw_img_url = urllib.parse.urljoin(base_url, raw_img)

        # 6. Recherche des Liens
        source_url = base_url
        external_url = ""

        links = soup_element.find_all("a", href=True)
        for a in links:
            href = a["href"].strip()
            full_href = urllib.parse.urljoin(base_url, href)

            text_link = a.get_text(strip=True).lower()
            classes_link = " ".join(a.get("class", [])).lower()

            is_action_link = any(k in text_link or k in classes_link or k in href.lower() for k in [
                "download", "telecharger", "télécharger", "get", "play", "jouer", "lien", "link", "external"
            ])

            if is_action_link and not external_url:
                external_url = full_href
            elif not source_url or source_url == base_url:
                source_url = full_href

        if not external_url and links:
            external_url = urllib.parse.urljoin(base_url, links[0]["href"])

        if not external_url:
            return None

        slug = generate_slug(title)

        return {
            "title": title,
            "normalized_title": normalize_text(title),
            "slug": slug,
            "description": description[:1000],
            "platform": detected_platform[:50],
            "category": category[:50],
            "raw_image_url": raw_img_url,
            "image_url": raw_img_url,  # Sera mis à jour avec Cloudinary lors de la publication
            "source_url": source_url,
            "external_url": external_url,
        }
    except Exception:
        return None


def scan_partner_site(partner: Dict[str, Any]) -> Dict[str, Any]:
    """Analyse complète d'un site partenaire."""
    base_url = partner["base_url"]
    partner_id = partner["id"]
    partner_name = partner["name"]
    allowed_domains = [d.strip() for d in (partner.get("allowed_domains") or "").split(",") if d.strip()]
    if not allowed_domains:
        allowed_domains = [extract_domain(base_url)]

    result = {
        "partner_id": partner_id,
        "partner_name": partner_name,
        "pages_scanned": 0,
        "games_detected": 0,
        "duplicates": 0,
        "invalid_links": 0,
        "candidates": [],
        "errors": []
    }

    try:
        resp = requests.get(base_url, headers=HEADERS, timeout=DEFAULT_TIMEOUT)
        result["pages_scanned"] += 1

        if resp.status_code != 200:
            result["errors"].append(f"Statut HTTP : {resp.status_code}")
            return result

        html_lower = resp.text.lower()
        if "captcha" in html_lower or ("cloudflare" in html_lower and "challenge" in html_lower):
            result["errors"].append("Protection technique ou CAPTCHA détecté.")
            return result

        soup = BeautifulSoup(resp.content, "html.parser")

        card_containers = (
            soup.find_all(class_=re.compile(r"(game|jeu|item|card|entry|post|article|product)", re.I))
            or soup.find_all("article")
        )

        detected_games = []
        for container in card_containers:
            game_data = parse_game_card(container, base_url, allowed_domains)
            if game_data and game_data["title"]:
                if not any(d["normalized_title"] == game_data["normalized_title"] for d in detected_games):
                    detected_games.append(game_data)

        result["games_detected"] = len(detected_games)

        for game in detected_games:
            # Vérification anti-doublon
            if is_game_duplicate(game):
                result["duplicates"] += 1
                continue

            # Validation du lien externe
            is_valid_link, reason = validate_external_link(game["external_url"], allowed_domains)
            if not is_valid_link:
                result["invalid_links"] += 1
                continue

            game["partner_id"] = partner_id
            game["partner_name"] = partner_name
            result["candidates"].append(game)

    except requests.exceptions.Timeout:
        result["errors"].append(f"Timeout sur {base_url}")
    except requests.exceptions.RequestException as e:
        result["errors"].append(f"Erreur réseau : {str(e)[:80]}")
    except Exception as e:
        result["errors"].append(f"Erreur d'analyse : {str(e)[:80]}")

    return result


# =============================================================================
# PUBLICATION DES JEUX
# =============================================================================

def publish_game(game: Dict[str, Any], db_path: Optional[str] = None) -> bool:
    """
    Publie une fiche de jeu :
    1. Téléverse la jaquette vers Cloudinary (si configuré).
    2. Enregistre dans autopilot_published.
    3. Met à jour la table games/jeux existante.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    today_str = date.today().isoformat()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        # Téléversement Cloudinary de l'image (avec fallback auto)
        final_image_url = game.get("raw_image_url") or game.get("image_url", "")
        if final_image_url:
            final_image_url = upload_image_to_cloudinary(final_image_url, game["slug"], db_path)

        # 1. Enregistrement dans autopilot_published
        cursor.execute("""
            INSERT INTO autopilot_published (
                game_title, normalized_title, slug, platform, category,
                image_url, source_url, external_url, published_date, created_at, partner_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            game["title"],
            game["normalized_title"],
            game["slug"],
            game.get("platform", "PC"),
            game.get("category", "Action"),
            final_image_url,
            game["source_url"],
            game["external_url"],
            today_str,
            now_str,
            game.get("partner_id")
        ))

        # 2. Insertion intelligente dans la table existante NovaGaming
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('games', 'jeux')")
        table_row = cursor.fetchone()
        if table_row:
            table_name = table_row[0]
            cursor.execute(f"PRAGMA table_info({table_name})")
            existing_cols = {col[1].lower(): col[1] for col in cursor.fetchall()}

            col_map = {}
            for candidate_key, col_val in [
                ("title", game["title"]),
                ("name", game["title"]),
                ("nom", game["title"]),
                ("slug", game["slug"]),
                ("description", game.get("description", "")),
                ("platform", game.get("platform", "PC")),
                ("plateforme", game.get("platform", "PC")),
                ("category", game.get("category", "Action")),
                ("categorie", game.get("category", "Action")),
                ("genre", game.get("category", "Action")),
                ("image_url", final_image_url),
                ("image", final_image_url),
                ("cover", final_image_url),
                ("download_url", game["external_url"]),
                ("external_url", game["external_url"]),
                ("lien", game["external_url"]),
                ("source_url", game["source_url"]),
                ("source", game["source_url"]),
                ("created_at", now_str),
                ("date_publication", now_str),
            ]:
                if candidate_key in existing_cols and existing_cols[candidate_key] not in col_map:
                    col_map[existing_cols[candidate_key]] = col_val

            if col_map:
                cols = list(col_map.keys())
                placeholders = ["?"] * len(cols)
                values = list(col_map.values())
                insert_sql = f"INSERT INTO {table_name} ({', '.join(cols)}) VALUES ({', '.join(placeholders)})"
                cursor.execute(insert_sql, tuple(values))

        # Mise à jour des statistiques du partenaire
        if game.get("partner_id"):
            cursor.execute("""
                UPDATE autopilot_partners
                SET total_found = total_found + 1, last_scanned_at = ?
                WHERE id = ?
            """, (now_str, game["partner_id"]))

        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"[AutoPilot Publish Error] {e}")
        return False
    finally:
        conn.close()


# =============================================================================
# FONCTION PRINCIPALE : RUN_DAILY_AUTOPILOT()
# =============================================================================

def run_daily_autopilot(db_path: Optional[str] = None, force: bool = False) -> Dict[str, Any]:
    """
    Exécute le cycle complet AutoPilot :
    - Vérification du statut et de la limite (DAILY_GAME_LIMIT = 2).
    - Analyse de tous les partenaires autorisés.
    - Publication automatique sécurisée.
    - Retourne les résultats complets pour Flask / Admin.
    """
    now = datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT value FROM autopilot_settings WHERE key = 'is_enabled'")
    row_enabled = cursor.fetchone()
    is_enabled = row_enabled["value"] == "1" if row_enabled else True

    if not is_enabled and not force:
        conn.close()
        return {
            "success": False,
            "status": "disabled",
            "message": "AutoPilot est actuellement désactivé.",
            "games_published": 0,
            "today_total": get_today_published_count(db_path),
            "daily_limit": DAILY_GAME_LIMIT
        }

    published_today = get_today_published_count(db_path)
    remaining_slots = max(0, DAILY_GAME_LIMIT - published_today)

    if remaining_slots == 0 and not force:
        conn.close()
        return {
            "success": True,
            "status": "limit_reached",
            "message": f"Limite journalière atteinte ({DAILY_GAME_LIMIT}/{DAILY_GAME_LIMIT} jeux publiés aujourd'hui).",
            "games_published": 0,
            "today_total": published_today,
            "daily_limit": DAILY_GAME_LIMIT
        }

    active_partners = get_active_partners(db_path)
    if not active_partners:
        conn.close()
        return {
            "success": False,
            "status": "no_partners",
            "message": "Aucun partenaire actif configuré.",
            "games_published": 0,
            "today_total": published_today,
            "daily_limit": DAILY_GAME_LIMIT
        }

    total_pages = 0
    total_detected = 0
    total_duplicates = 0
    total_invalid_links = 0
    all_candidates: List[Dict[str, Any]] = []
    all_errors: List[str] = []

    for partner in active_partners:
        scan_res = scan_partner_site(partner)
        total_pages += scan_res["pages_scanned"]
        total_detected += scan_res["games_detected"]
        total_duplicates += scan_res["duplicates"]
        total_invalid_links += scan_res["invalid_links"]
        all_candidates.extend(scan_res["candidates"])
        all_errors.extend(scan_res["errors"])

    published_games: List[Dict[str, Any]] = []
    candidates_to_publish = all_candidates[:remaining_slots]

    for candidate in candidates_to_publish:
        if not is_game_duplicate(candidate, db_path):
            if publish_game(candidate, db_path):
                published_games.append(candidate)

    new_published_count = len(published_games)
    new_today_total = published_today + new_published_count

    next_run_dt = (now + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
    next_run_str = next_run_dt.strftime("%d/%m/%Y %H:%M")

    cursor.execute("UPDATE autopilot_settings SET value = ? WHERE key = 'last_run'", (now_str,))
    cursor.execute("UPDATE autopilot_settings SET value = ? WHERE key = 'next_run'", (next_run_str,))

    status_str = "SUCCESS" if new_published_count > 0 else ("NO_NEW_GAMES" if total_detected > 0 else "SCAN_EMPTY")
    details = json.dumps({
        "errors": all_errors,
        "published_titles": [g["title"] for g in published_games],
        "candidates_count": len(all_candidates)
    }, ensure_ascii=False)

    cursor.execute("""
        INSERT INTO autopilot_logs (
            timestamp, partner_id, partner_name, pages_scanned, games_detected,
            duplicates_count, invalid_links_count, games_published_count, status, details_json
        ) VALUES (?, NULL, 'Tous les partenaires', ?, ?, ?, ?, ?, ?, ?)
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
    conn.close()

    return {
        "success": True,
        "status": status_str,
        "message": f"Analyse terminée. {new_published_count} jeu(x) publié(s) aujourd'hui ({new_today_total}/{DAILY_GAME_LIMIT}).",
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


# =============================================================================
# STATUT & VARIABLES POUR FLASK (render_template)
# =============================================================================

def get_autopilot_status(db_path: Optional[str] = None) -> Dict[str, Any]:
    """Retourne toutes les variables formatées pour le template Jinja admin_ai.html."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT value FROM autopilot_settings WHERE key = 'is_enabled'")
    row_en = cursor.fetchone()
    is_enabled = row_en["value"] == "1" if row_en else True
    status_label = "active" if is_enabled else "inactive"

    cursor.execute("SELECT value FROM autopilot_settings WHERE key = 'last_run'")
    row_last = cursor.fetchone()
    raw_last = row_last["value"] if row_last else ""
    if raw_last:
        try:
            dt_last = datetime.strptime(raw_last, "%Y-%m-%d %H:%M:%S")
            last_run = dt_last.strftime("%d/%m/%Y %H:%M")
        except Exception:
            last_run = raw_last
    else:
        last_run = "Aucune analyse récente"

    cursor.execute("SELECT value FROM autopilot_settings WHERE key = 'next_run'")
    row_next = cursor.fetchone()
    next_run = row_next["value"] if row_next and row_next["value"] else "Demain à 10:00"

    cursor.execute("SELECT * FROM autopilot_partners ORDER BY id DESC")
    partners = [dict(r) for r in cursor.fetchall()]

    cursor.execute("SELECT * FROM autopilot_logs ORDER BY id DESC LIMIT 20")
    raw_logs = [dict(r) for r in cursor.fetchall()]

    cursor.execute("""
        SELECT 
            COALESCE(SUM(pages_scanned), 0) AS total_pages,
            COALESCE(SUM(games_detected), 0) AS total_detected,
            COALESCE(SUM(duplicates_count), 0) AS total_duplicates,
            COALESCE(SUM(invalid_links_count), 0) AS total_invalid_links,
            COALESCE(SUM(games_published_count), 0) AS total_published
        FROM autopilot_logs
    """)
    stat_row = cursor.fetchone()
    stats = {
        "pages_scanned": stat_row["total_pages"] if stat_row else 0,
        "games_detected": stat_row["total_detected"] if stat_row else 0,
        "duplicates": stat_row["total_duplicates"] if stat_row else 0,
        "invalid_links": stat_row["total_invalid_links"] if stat_row else 0,
        "games_published": stat_row["total_published"] if stat_row else 0,
        "errors": 0
    }

    games_today = get_today_published_count(db_path)
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


def toggle_autopilot_status(enable: Optional[bool] = None, db_path: Optional[str] = None) -> bool:
    """Active ou désactive l'AutoPilot."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    try:
        if enable is None:
            cursor.execute("SELECT value FROM autopilot_settings WHERE key = 'is_enabled'")
            row = cursor.fetchone()
            current = row["value"] == "1" if row else True
            new_val = "0" if current else "1"
        else:
            new_val = "1" if enable else "0"

        cursor.execute("UPDATE autopilot_settings SET value = ? WHERE key = 'is_enabled'", (new_val,))
        conn.commit()
        return new_val == "1"
    except Exception:
        return False
    finally:
        conn.close()
