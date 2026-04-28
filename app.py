import os
import sqlite3
from datetime import datetime
from functools import wraps

from flask import (Flask, flash, jsonify, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "artvault_secret_key_change_in_production"  # Change this in production!

# Where uploaded images will be stored
UPLOAD_FOLDER = os.path.join("static", "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE

# Make sure the uploads folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def get_db():
    """Open a connection to the SQLite database."""
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row   # Rows behave like dicts
    return conn


def init_db():
    """Create all tables if they don't already exist."""
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT    NOT NULL UNIQUE,
            email    TEXT    NOT NULL UNIQUE,
            password TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS artworks (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            title      TEXT    NOT NULL,
            image_path TEXT    NOT NULL,
            category   TEXT    NOT NULL DEFAULT 'Other',
            created_at TEXT    NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS likes (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            artwork_id INTEGER NOT NULL,
            UNIQUE (user_id, artwork_id),         -- one like per user per artwork
            FOREIGN KEY (user_id)    REFERENCES users(id),
            FOREIGN KEY (artwork_id) REFERENCES artworks(id)
        );

        CREATE TABLE IF NOT EXISTS comments (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL,
            artwork_id   INTEGER NOT NULL,
            comment_text TEXT    NOT NULL,
            created_at   TEXT    NOT NULL,
            FOREIGN KEY (user_id)    REFERENCES users(id),
            FOREIGN KEY (artwork_id) REFERENCES artworks(id)
        );
    """)
    db.commit()
    db.close()

def allowed_file(filename):
    """Return True only if the file has an allowed image extension."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def login_required(f):
    """Redirect to login page if the user is not logged in."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Login required"}), 401
        return f(*args, **kwargs)
    return decorated

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/login")
def login_page():
    return render_template("login.html")

@app.route("/signup")
def signup_page():
    return render_template("signup.html")

@app.route("/upload")
def upload_page():
    return render_template("upload.html")

@app.route("/profile")
def profile_page():
    return render_template("profile.html")

@app.route("/artwork/<int:artwork_id>")
def artwork_page(artwork_id):
    return render_template("artwork.html", artwork_id=artwork_id)

@app.route("/signup", methods=["POST"])
def signup():
    """
    Register a new user.
    Expects JSON: { username, email, password }
    """
    data = request.get_json()

    username = data.get("username", "").strip()
    email    = data.get("email", "").strip().lower()
    password = data.get("password", "")

    # Basic validation
    if not username or not email or not password:
        return jsonify({"error": "All fields are required"}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    db = get_db()
    try:
        # Hash the password before storing (never store plain text!)
        hashed_pw = generate_password_hash(password)
        db.execute(
            "INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
            (username, email, hashed_pw)
        )
        db.commit()
        return jsonify({"message": "Account created! Please log in."}), 201
    except sqlite3.IntegrityError:
        return jsonify({"error": "Username or email already exists"}), 409
    finally:
        db.close()

@app.route("/login", methods=["POST"])
def login():
    """
    Log in an existing user.
    Expects JSON: { email, password }
    Sets session variables on success.
    """
    data = request.get_json()
    email    = data.get("email", "").strip().lower()
    password = data.get("password", "")

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    db.close()

    if user and check_password_hash(user["password"], password):
        # Store user info in the session (server-side cookie)
        session["user_id"]  = user["id"]
        session["username"] = user["username"]
        return jsonify({"message": "Login successful", "username": user["username"]})

    return jsonify({"error": "Invalid email or password"}), 401


@app.route("/logout")
def logout():
    """Clear the session and log out."""
    session.clear()
    return redirect(url_for("index"))

@app.route("/me")
def me():
    """Return current session info (used by frontend to check login state)."""
    if "user_id" in session:
        return jsonify({"logged_in": True, "user_id": session["user_id"], "username": session["username"]})
    return jsonify({"logged_in": False})

# ── ARTWORK API routes ───

@app.route("/upload-art", methods=["POST"])
@login_required
def upload_art():
    """
    Upload a new artwork.
    Expects multipart/form-data: title, category, image (file)
    """
    title    = request.form.get("title", "").strip()
    category = request.form.get("category", "Other").strip()
    image    = request.files.get("image")

    if not title or not image:
        return jsonify({"error": "Title and image are required"}), 400

    if not allowed_file(image.filename):
        return jsonify({"error": "Only PNG, JPG, GIF, WEBP files allowed"}), 400

    # Build a safe unique filename: timestamp + original name
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    filename  = f"{timestamp}_{secure_filename(image.filename)}"
    save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    image.save(save_path)

    # Store relative path in DB so we can build a URL later
    image_path = f"static/uploads/{filename}"

    db = get_db()
    db.execute(
        "INSERT INTO artworks (user_id, title, image_path, category, created_at) VALUES (?, ?, ?, ?, ?)",
        (session["user_id"], title, image_path, category, datetime.now().isoformat())
    )
    db.commit()
    db.close()
    return jsonify({"message": "Artwork uploaded successfully!"}), 201


@app.route("/artworks")
def get_artworks():
    """
    Return all artworks with like count and author username.
    Optional query params:
        q        → search by title
        category → filter by category
    """
    q        = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()

    db  = get_db()
    sql = """
        SELECT a.id, a.title, a.image_path, a.category, a.created_at,
               u.username,
               COUNT(l.id) AS like_count
        FROM artworks a
        JOIN users u ON a.user_id = u.id
        LEFT JOIN likes l ON a.id = l.artwork_id
        WHERE 1=1
    """
    params = []

    if q:
        sql += " AND a.title LIKE ?"
        params.append(f"%{q}%")

    if category and category != "All":
        sql += " AND a.category = ?"
        params.append(category)

    sql += " GROUP BY a.id ORDER BY a.created_at DESC"

    rows = db.execute(sql, params).fetchall()

    # Add whether the current user has liked each artwork
    user_id   = session.get("user_id")
    user_likes = set()
    if user_id:
        liked = db.execute("SELECT artwork_id FROM likes WHERE user_id = ?", (user_id,)).fetchall()
        user_likes = {row["artwork_id"] for row in liked}

    db.close()

    artworks = []
    for row in rows:
        artworks.append({
            "id":         row["id"],
            "title":      row["title"],
            "image_path": "/" + row["image_path"],   # make it a root-relative URL
            "category":   row["category"],
            "created_at": row["created_at"],
            "username":   row["username"],
            "like_count": row["like_count"],
            "liked":      row["id"] in user_likes,
        })

    return jsonify(artworks)


@app.route("/artwork/<int:artwork_id>")
def get_artwork(artwork_id):
    """Return a single artwork with its comments."""
    db      = get_db()
    artwork = db.execute("""
        SELECT a.*, u.username,
               COUNT(DISTINCT l.id) AS like_count
        FROM artworks a
        JOIN users u ON a.user_id = u.id
        LEFT JOIN likes l ON a.id = l.artwork_id
        WHERE a.id = ?
        GROUP BY a.id
    """, (artwork_id,)).fetchone()

    if not artwork:
        db.close()
        return jsonify({"error": "Artwork not found"}), 404

    comments = db.execute("""
        SELECT c.comment_text, c.created_at, u.username
        FROM comments c
        JOIN users u ON c.user_id = u.id
        WHERE c.artwork_id = ?
        ORDER BY c.created_at
    """, (artwork_id,)).fetchall()

    user_id = session.get("user_id")
    liked   = False
    if user_id:
        like = db.execute("SELECT id FROM likes WHERE user_id=? AND artwork_id=?",
                          (user_id, artwork_id)).fetchone()
        liked = like is not None

    db.close()
    return jsonify({
        "id":         artwork["id"],
        "title":      artwork["title"],
        "image_path": "/" + artwork["image_path"],
        "category":   artwork["category"],
        "created_at": artwork["created_at"],
        "username":   artwork["username"],
        "like_count": artwork["like_count"],
        "liked":      liked,
        "comments": [
            {"username": c["username"], "text": c["comment_text"], "created_at": c["created_at"]}
            for c in comments
        ],
    })


@app.route("/edit-art/<int:artwork_id>", methods=["PUT"])
@login_required
def edit_art(artwork_id):
    """
    Edit an artwork's title and/or category.
    Only the owner can edit.
    Expects JSON: { title, category }
    """
    db      = get_db()
    artwork = db.execute("SELECT * FROM artworks WHERE id = ?", (artwork_id,)).fetchone()

    if not artwork:
        db.close()
        return jsonify({"error": "Artwork not found"}), 404
    if artwork["user_id"] != session["user_id"]:
        db.close()
        return jsonify({"error": "Not authorized"}), 403

    data     = request.get_json()
    title    = data.get("title", artwork["title"]).strip()
    category = data.get("category", artwork["category"]).strip()

    if not title:
        db.close()
        return jsonify({"error": "Title cannot be empty"}), 400

    db.execute("UPDATE artworks SET title=?, category=? WHERE id=?", (title, category, artwork_id))
    db.commit()
    db.close()
    return jsonify({"message": "Artwork updated!"})


@app.route("/delete-art/<int:artwork_id>", methods=["DELETE"])
@login_required
def delete_art(artwork_id):
    """
    Delete an artwork and its file from disk.
    Only the owner can delete.
    """
    db      = get_db()
    artwork = db.execute("SELECT * FROM artworks WHERE id = ?", (artwork_id,)).fetchone()

    if not artwork:
        db.close()
        return jsonify({"error": "Artwork not found"}), 404
    if artwork["user_id"] != session["user_id"]:
        db.close()
        return jsonify({"error": "Not authorized"}), 403

    # Delete the image file from disk
    file_path = artwork["image_path"]
    if os.path.exists(file_path):
        os.remove(file_path)

    # Cascade delete: remove likes + comments first, then the artwork
    db.execute("DELETE FROM likes    WHERE artwork_id = ?", (artwork_id,))
    db.execute("DELETE FROM comments WHERE artwork_id = ?", (artwork_id,))
    db.execute("DELETE FROM artworks WHERE id = ?",         (artwork_id,))
    db.commit()
    db.close()
    return jsonify({"message": "Artwork deleted"})



