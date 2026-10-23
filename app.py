"""
Smart Agriculture Sensor Dashboard
Flask backend + SQLite + REST API + session-based authentication.

ESP32 sensor nodes (or the included simulator) POST readings to the API.
The dashboard page polls the API every 5 seconds to show live values.
"""

import os
import sqlite3
from functools import wraps

from flask import (Flask, g, jsonify, redirect, render_template, request,
                   session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

DEFAULT_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agri.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL,
    soil_moisture REAL NOT NULL,
    temperature REAL NOT NULL,
    light REAL NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_readings_device_time
    ON readings (device_id, created_at);
"""

# Valid ranges used for data validation
LIMITS = {
    "soil_moisture": (0, 100),    # percent
    "temperature": (-40, 85),     # degrees Celsius
    "light": (0, 100000),         # lux
}


def create_app(db_path=None):
    app = Flask(__name__)
    app.config["DATABASE"] = db_path or os.environ.get("DATABASE", DEFAULT_DB)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-change-me")

    # ---------- Database helpers ----------
    def get_db():
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DATABASE"])
            g.db.row_factory = sqlite3.Row
        return g.db

    @app.teardown_appcontext
    def close_db(_exc):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    init_conn = sqlite3.connect(app.config["DATABASE"])
    try:
        init_conn.executescript(SCHEMA)
        init_conn.commit()
    finally:
        init_conn.close()

    # ---------- Auth helpers ----------
    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if "user_id" not in session:
                if request.path.startswith("/api/"):
                    return jsonify(error="authentication required"), 401
                return redirect(url_for("login"))
            return view(*args, **kwargs)
        return wrapped

    # ---------- Pages ----------
    @app.route("/")
    @login_required
    def dashboard():
        return render_template("dashboard.html", username=session["username"])

    @app.route("/register", methods=["GET", "POST"])
    def register():
        error = None
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            if len(username) < 3:
                error = "Username must be at least 3 characters."
            elif len(password) < 6:
                error = "Password must be at least 6 characters."
            else:
                try:
                    db = get_db()
                    db.execute(
                        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                        (username, generate_password_hash(password)),
                    )
                    db.commit()
                    return redirect(url_for("login"))
                except sqlite3.IntegrityError:
                    error = "That username is already taken."
        return render_template("auth.html", title="Register", error=error,
                               action=url_for("register"),
                               other_url=url_for("login"), other_text="Log in")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        error = None
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            user = get_db().execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
            if user and check_password_hash(user["password_hash"], password):
                session.clear()
                session["user_id"] = user["id"]
                session["username"] = user["username"]
                return redirect(url_for("dashboard"))
            error = "Invalid username or password."
        return render_template("auth.html", title="Log in", error=error,
                               action=url_for("login"),
                               other_url=url_for("register"),
                               other_text="Create an account")

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    # ---------- REST API ----------
    def validate_reading(data):
        """Return (clean_dict, error_message)."""
        if not isinstance(data, dict):
            return None, "JSON body required"
        device_id = data.get("device_id")
        if not isinstance(device_id, str) or not device_id.strip():
            return None, "device_id is required"
        if len(device_id) > 50:
            return None, "device_id too long"
        clean = {"device_id": device_id.strip()}
        for field, (low, high) in LIMITS.items():
            value = data.get(field)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return None, f"{field} must be a number"
            if not (low <= value <= high):
                return None, f"{field} must be between {low} and {high}"
            clean[field] = float(value)
        return clean, None

    @app.route("/api/readings", methods=["POST"])
    @login_required
    def add_reading():
        clean, error = validate_reading(request.get_json(silent=True))
        if error:
            return jsonify(error=error), 400
        db = get_db()
        cur = db.execute(
            "INSERT INTO readings (device_id, soil_moisture, temperature, light) "
            "VALUES (?, ?, ?, ?)",
            (clean["device_id"], clean["soil_moisture"],
             clean["temperature"], clean["light"]),
        )
        db.commit()
        return jsonify(id=cur.lastrowid, **clean), 201

    @app.route("/api/readings", methods=["GET"])
    @login_required
    def list_readings():
        device_id = request.args.get("device_id")
        try:
            limit = int(request.args.get("limit", 50))
        except ValueError:
            return jsonify(error="limit must be an integer"), 400
        limit = max(1, min(limit, 500))
        sql = "SELECT * FROM readings"
        params = []
        if device_id:
            sql += " WHERE device_id = ?"
            params.append(device_id)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        rows = get_db().execute(sql, params).fetchall()
        return jsonify([dict(r) for r in rows])

    @app.route("/api/latest", methods=["GET"])
    @login_required
    def latest():
        """Most recent reading for every device."""
        rows = get_db().execute(
            "SELECT r.* FROM readings r "
            "JOIN (SELECT device_id, MAX(id) AS max_id FROM readings "
            "      GROUP BY device_id) m ON r.id = m.max_id "
            "ORDER BY r.device_id"
        ).fetchall()
        return jsonify([dict(r) for r in rows])

    @app.route("/health")
    def health():
        return jsonify(status="ok")

    return app


# Used by Gunicorn: `gunicorn app:app`
app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
