import os
import sqlite3
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, abort, flash

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "data.db")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")

# Administration commune aux deux sites
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "monetise4@gmail.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "monetise4@gmail.com")

def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ppsspp_games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            image TEXT DEFAULT '',
            description TEXT DEFAULT '',
            size TEXT DEFAULT '',
            download_url TEXT NOT NULL,
            active INTEGER DEFAULT 1,
            downloads INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            logo TEXT DEFAULT '',
            description TEXT DEFAULT '',
            stream_url TEXT NOT NULL,
            active INTEGER DEFAULT 1,
            views INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS visitors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            section TEXT NOT NULL,
            country TEXT DEFAULT 'Unknown',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin_login"))
        return fn(*args, **kwargs)
    return wrapper

@app.before_request
def track_public_visit():
    if (
        request.endpoint
        and not request.path.startswith("/admin")
        and request.endpoint != "static"
    ):
        section = "ppsspp" if request.path.startswith("/ppsspp") else "flux"
        country = request.headers.get("CF-IPCountry", "Unknown")[:80]
        conn = db()
        conn.execute(
            "INSERT INTO visitors(section,country) VALUES(?,?)",
            (section, country)
        )
        conn.commit()
        conn.close()

# ---------------- PUBLIC PPSSPP ----------------

@app.route("/")
def root():
    return redirect(url_for("ppsspp_home"))

@app.route("/ppsspp")
def ppsspp_home():
    conn = db()
    games = conn.execute(
        "SELECT * FROM ppsspp_games WHERE active=1 ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return render_template("ppsspp_home.html", games=games)

@app.route("/ppsspp/<int:game_id>")
def ppsspp_detail(game_id):
    conn = db()
    game = conn.execute(
        "SELECT * FROM ppsspp_games WHERE id=? AND active=1",
        (game_id,)
    ).fetchone()
    conn.close()
    if not game:
        abort(404)
    return render_template("ppsspp_detail.html", game=game)

@app.route("/ppsspp/<int:game_id>/download")
def ppsspp_download(game_id):
    conn = db()
    game = conn.execute(
        "SELECT * FROM ppsspp_games WHERE id=? AND active=1",
        (game_id,)
    ).fetchone()
    if not game:
        conn.close()
        abort(404)

    conn.execute(
        "UPDATE ppsspp_games SET downloads=downloads+1 WHERE id=?",
        (game_id,)
    )
    conn.commit()
    conn.close()

    # Le site ne stocke pas le jeu : il redirige vers le lien externe fourni.
    return redirect(game["download_url"])

# ---------------- PUBLIC FLUX ----------------

@app.route("/flux")
def flux_home():
    conn = db()
    channels = conn.execute(
        "SELECT * FROM channels WHERE active=1 ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return render_template("flux_home.html", channels=channels)

@app.route("/flux/<int:channel_id>")
def flux_watch(channel_id):
    conn = db()
    channel = conn.execute(
        "SELECT * FROM channels WHERE id=? AND active=1",
        (channel_id,)
    ).fetchone()
    if not channel:
        conn.close()
        abort(404)

    conn.execute(
        "UPDATE channels SET views=views+1 WHERE id=?",
        (channel_id,)
    )
    conn.commit()
    conn.close()

    return render_template("flux_watch.html", channel=channel)

# ---------------- ADMIN COMMUN ----------------

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if (
            request.form.get("username") == ADMIN_USERNAME
            and request.form.get("password") == ADMIN_PASSWORD
        ):
            session["admin"] = True
            return redirect(url_for("admin_dashboard"))

        flash("Identifiants incorrects.", "error")

    return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))

@app.route("/admin")
@admin_required
def admin_dashboard():
    conn = db()

    games = conn.execute(
        "SELECT * FROM ppsspp_games ORDER BY id DESC"
    ).fetchall()

    channels = conn.execute(
        "SELECT * FROM channels ORDER BY id DESC"
    ).fetchall()

    ppsspp_downloads = conn.execute(
        "SELECT COALESCE(SUM(downloads),0) n FROM ppsspp_games"
    ).fetchone()["n"]

    flux_views = conn.execute(
        "SELECT COALESCE(SUM(views),0) n FROM channels"
    ).fetchone()["n"]

    visitors = conn.execute(
        "SELECT COUNT(*) n FROM visitors"
    ).fetchone()["n"]

    countries = conn.execute("""
        SELECT country, COUNT(*) n
        FROM visitors
        GROUP BY country
        ORDER BY n DESC
        LIMIT 20
    """).fetchall()

    conn.close()

    return render_template(
        "admin_dashboard.html",
        games=games,
        channels=channels,
        ppsspp_downloads=ppsspp_downloads,
        flux_views=flux_views,
        visitors=visitors,
        countries=countries
    )

# ---------- ADMIN PPSSPP ----------

@app.route("/admin/ppsspp/add", methods=["GET", "POST"])
@admin_required
def admin_ppsspp_add():
    if request.method == "POST":
        values = [
            request.form.get("name", "").strip(),
            request.form.get("image", "").strip(),
            request.form.get("description", "").strip(),
            request.form.get("size", "").strip(),
            request.form.get("download_url", "").strip()
        ]

        if not values[0] or not values[4]:
            flash("Le nom et le lien externe sont obligatoires.", "error")
            return render_template("admin_game_form.html", game=None)

        conn = db()
        conn.execute("""
            INSERT INTO ppsspp_games
            (name,image,description,size,download_url)
            VALUES (?,?,?,?,?)
        """, values)
        conn.commit()
        conn.close()
        return redirect(url_for("admin_dashboard"))

    return render_template("admin_game_form.html", game=None)

@app.route("/admin/ppsspp/<int:game_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_ppsspp_edit(game_id):
    conn = db()
    game = conn.execute(
        "SELECT * FROM ppsspp_games WHERE id=?",
        (game_id,)
    ).fetchone()

    if not game:
        conn.close()
        abort(404)

    if request.method == "POST":
        values = [
            request.form.get("name", "").strip(),
            request.form.get("image", "").strip(),
            request.form.get("description", "").strip(),
            request.form.get("size", "").strip(),
            request.form.get("download_url", "").strip()
        ]

        conn.execute("""
            UPDATE ppsspp_games
            SET name=?, image=?, description=?, size=?, download_url=?
            WHERE id=?
        """, (*values, game_id))
        conn.commit()
        conn.close()
        return redirect(url_for("admin_dashboard"))

    conn.close()
    return render_template("admin_game_form.html", game=game)

@app.post("/admin/ppsspp/<int:game_id>/toggle")
@admin_required
def admin_ppsspp_toggle(game_id):
    conn = db()
    conn.execute(
        "UPDATE ppsspp_games SET active=1-active WHERE id=?",
        (game_id,)
    )
    conn.commit()
    conn.close()
    return redirect(url_for("admin_dashboard"))

@app.post("/admin/ppsspp/<int:game_id>/delete")
@admin_required
def admin_ppsspp_delete(game_id):
    conn = db()
    conn.execute("DELETE FROM ppsspp_games WHERE id=?", (game_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin_dashboard"))

# ---------- ADMIN FLUX ----------

@app.route("/admin/flux/add", methods=["GET", "POST"])
@admin_required
def admin_flux_add():
    if request.method == "POST":
        values = [
            request.form.get("name", "").strip(),
            request.form.get("logo", "").strip(),
            request.form.get("description", "").strip(),
            request.form.get("stream_url", "").strip()
        ]

        if not values[0] or not values[3]:
            flash("Le nom et le flux sont obligatoires.", "error")
            return render_template("admin_channel_form.html", channel=None)

        conn = db()
        conn.execute("""
            INSERT INTO channels(name,logo,description,stream_url)
            VALUES(?,?,?,?)
        """, values)
        conn.commit()
        conn.close()
        return redirect(url_for("admin_dashboard"))

    return render_template("admin_channel_form.html", channel=None)

@app.route("/admin/flux/<int:channel_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_flux_edit(channel_id):
    conn = db()
    channel = conn.execute(
        "SELECT * FROM channels WHERE id=?",
        (channel_id,)
    ).fetchone()

    if not channel:
        conn.close()
        abort(404)

    if request.method == "POST":
        values = [
            request.form.get("name", "").strip(),
            request.form.get("logo", "").strip(),
            request.form.get("description", "").strip(),
            request.form.get("stream_url", "").strip()
        ]

        conn.execute("""
            UPDATE channels
            SET name=?, logo=?, description=?, stream_url=?
            WHERE id=?
        """, (*values, channel_id))
        conn.commit()
        conn.close()
        return redirect(url_for("admin_dashboard"))

    conn.close()
    return render_template("admin_channel_form.html", channel=channel)

@app.post("/admin/flux/<int:channel_id>/toggle")
@admin_required
def admin_flux_toggle(channel_id):
    conn = db()
    conn.execute(
        "UPDATE channels SET active=1-active WHERE id=?",
        (channel_id,)
    )
    conn.commit()
    conn.close()
    return redirect(url_for("admin_dashboard"))

@app.post("/admin/flux/<int:channel_id>/delete")
@admin_required
def admin_flux_delete(channel_id):
    conn = db()
    conn.execute("DELETE FROM channels WHERE id=?", (channel_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin_dashboard"))

@app.errorhandler(404)
def not_found(_):
    return render_template("404.html"), 404

init_db()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False
    )
