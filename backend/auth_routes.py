from flask import Blueprint, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

def get_db():
    return psycopg2.connect(
        dbname="your_db",
        user="your_user",
        password="your_pass",
        host="localhost"
    )

#signup route
@auth_bp.route("/signup", methods=["POST"])
def signup():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Missing fields"}), 400

    hashed = generate_password_hash(password)

    conn = get_db()
    cur = conn.cursor()

    try:
        cur.execute(
            "INSERT INTO users (email, password_hash) VALUES (%s, %s) RETURNING id",
            (email.lower(), hashed)
        )
        user_id = cur.fetchone()[0]
        conn.commit()

        session["user_id"] = str(user_id)

        return jsonify({"message": "New account created!"}), 201

    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        return jsonify({"error": "Email already exists"}), 400

    finally:
        cur.close()
        conn.close()

#login route
@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT id, password_hash FROM users WHERE email = %s", (email.lower(),))
    user = cur.fetchone()

    cur.close()
    conn.close()

    if not user or not check_password_hash(user[1], password):
        return jsonify({"error": "Invalid credentials"}), 401

    session["user_id"] = str(user[0])

    return jsonify({"message": "Logged in!"})

#logout route
@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "Logged out"})
