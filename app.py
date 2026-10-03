import os, sqlite3
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, jsonify

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "CHANGE_ME")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "monetise4@gmail.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "CHANGE_ME")
DB = os.path.join(os.path.dirname(__file__), "data.db")

def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    c = db()
    c.execute("""CREATE TABLE IF NOT EXISTS channels(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        stream_url TEXT NOT NULL,
        logo TEXT DEFAULT '',
        description TEXT DEFAULT '',
        start_date TEXT DEFAULT '',
        end_date TEXT DEFAULT '',
        start_time TEXT DEFAULT '',
        end_time TEXT DEFAULT '',
        days TEXT DEFAULT '0,1,2,3,4,5,6',
        active INTEGER DEFAULT 1,
        created_at TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS views(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel_id INTEGER,
        country TEXT,
        user_agent TEXT,
        created_at TEXT
    )""")
    c.commit()
    c.close()

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin_login"))
        return fn(*args, **kwargs)
    return wrapper

def channel_active(ch):
    if not ch["active"]:
        return False
    now = datetime.now()
    today = now.date().isoformat()
    if ch["start_date"] and today < ch["start_date"]:
        return False
    if ch["end_date"] and today > ch["end_date"]:
        return False
    if ch["days"]:
        allowed = {int(x) for x in ch["days"].split(",") if x.strip().isdigit()}
        if now.weekday() not in allowed:
            return False
    if ch["start_time"] and ch["end_time"]:
        current = now.strftime("%H:%M")
        if not (ch["start_time"] <= current <= ch["end_time"]):
            return False
    return True

@app.route("/")
def home():
    c = db()
    rows = c.execute("SELECT * FROM channels ORDER BY id DESC").fetchall()
    c.close()
    channels = [dict(x) for x in rows if channel_active(x)]
    return render_template("home.html", channels=channels)

@app.route("/watch/<int:channel_id>")
def watch(channel_id):
    c = db()
    ch = c.execute("SELECT * FROM channels WHERE id=?", (channel_id,)).fetchone()
    if not ch or not channel_active(ch):
        c.close()
        return render_template("unavailable.html"), 404
    c.execute("""INSERT INTO views(channel_id,country,user_agent,created_at)
                 VALUES(?,?,?,?)""",
              (channel_id,
               request.headers.get("CF-IPCountry", "Unknown"),
               request.headers.get("User-Agent", ""),
               datetime.utcnow().isoformat()))
    c.commit()
    c.close()
    return render_template("watch.html", ch=ch)

@app.route("/admin/login", methods=["GET","POST"])
def admin_login():
    error = None
    if request.method == "POST":
        if request.form.get("email") == ADMIN_EMAIL and request.form.get("password") == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect(url_for("admin"))
        error = "Identifiants incorrects."
    return render_template("login.html", error=error)

@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))

@app.route("/admin")
@admin_required
def admin():
    c = db()
    channels = c.execute("SELECT * FROM channels ORDER BY id DESC").fetchall()
    total_views = c.execute("SELECT COUNT(*) n FROM views").fetchone()["n"]
    today_views = c.execute(
        "SELECT COUNT(*) n FROM views WHERE date(created_at)=date('now')"
    ).fetchone()["n"]
    stats = c.execute("""SELECT channels.name, COUNT(views.id) AS total
                         FROM channels LEFT JOIN views ON channels.id=views.channel_id
                         GROUP BY channels.id ORDER BY total DESC""").fetchall()
    countries = c.execute("""SELECT country, COUNT(*) total FROM views
                             GROUP BY country ORDER BY total DESC LIMIT 20""").fetchall()
    c.close()
    return render_template("admin.html", channels=channels,
                           total_views=total_views, today_views=today_views,
                           stats=stats, countries=countries)

def form_data():
    return (
        request.form.get("name","").strip(),
        request.form.get("stream_url","").strip(),
        request.form.get("logo","").strip(),
        request.form.get("description","").strip(),
        request.form.get("start_date",""),
        request.form.get("end_date",""),
        request.form.get("start_time",""),
        request.form.get("end_time",""),
        request.form.get("days","0,1,2,3,4,5,6")
    )

@app.route("/admin/channel/add", methods=["POST"])
@admin_required
def add_channel():
    data = form_data()
    if not data[0] or not data[1]:
        return redirect(url_for("admin"))
    c = db()
    c.execute("""INSERT INTO channels
        (name,stream_url,logo,description,start_date,end_date,start_time,end_time,days,active,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,1,?)""", (*data, datetime.utcnow().isoformat()))
    c.commit()
    c.close()
    return redirect(url_for("admin"))

@app.route("/admin/channel/<int:channel_id>/edit", methods=["GET","POST"])
@admin_required
def edit_channel(channel_id):
    c = db()
    ch = c.execute("SELECT * FROM channels WHERE id=?", (channel_id,)).fetchone()
    if not ch:
        c.close()
        return "Chaîne introuvable", 404
    if request.method == "POST":
        data = form_data()
        c.execute("""UPDATE channels SET name=?,stream_url=?,logo=?,description=?,
            start_date=?,end_date=?,start_time=?,end_time=?,days=? WHERE id=?""",
            (*data, channel_id))
        c.commit()
        c.close()
        return redirect(url_for("admin"))
    c.close()
    return render_template("edit.html", ch=ch)

@app.route("/admin/channel/<int:channel_id>/toggle")
@admin_required
def toggle_channel(channel_id):
    c = db()
    c.execute("UPDATE channels SET active=CASE active WHEN 1 THEN 0 ELSE 1 END WHERE id=?",
              (channel_id,))
    c.commit()
    c.close()
    return redirect(url_for("admin"))

@app.route("/admin/channel/<int:channel_id>/delete", methods=["POST"])
@admin_required
def delete_channel(channel_id):
    c = db()
    c.execute("DELETE FROM views WHERE channel_id=?", (channel_id,))
    c.execute("DELETE FROM channels WHERE id=?", (channel_id,))
    c.commit()
    c.close()
    return redirect(url_for("admin"))

@app.route("/api/channels")
def api_channels():
    c = db()
    rows = c.execute("SELECT * FROM channels ORDER BY id DESC").fetchall()
    c.close()
    return jsonify([dict(x) for x in rows if channel_active(x)])

init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",5000)))
