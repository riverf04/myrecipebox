from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, current_app
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import sys
import jwt
from app.db import get_db

auth_bp = Blueprint(
    "auth",
    __name__,
)


@auth_bp.post("/register")
def register():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object"}), 400

    username = data.get("username")
    email = data.get("email")
    password = data.get("password")

    if (
        not isinstance(username, str)
        or not username.strip()
        or not isinstance(email, str)
        or not email.strip()
        or not isinstance(password, str)
        or not password.strip()
    ):
        return jsonify({"error": "username, email, and password are required"}), 400

    password_hash = generate_password_hash(password)

    db = get_db()
    try:
        cursor = db.execute(
            """
            INSERT INTO users (username, email, password_hash)
            VALUES (?, ?, ?)
            """,
            (username.strip(), email.strip(), password_hash),
        )
        db.commit()
    except sqlite3.IntegrityError as e:
        print("DEBUG register IntegrityError:", e, file=sys.stderr)
        return jsonify({"error": "username or email already exists"}), 409

    return (
        jsonify(
            {
                "id": cursor.lastrowid,
                "username": username.strip(),
                "email": email.strip(),
            }
        ),
        201,
    )


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object"}), 400

    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    db = get_db()
    user = db.execute(
        "SELECT id, username, password_hash, role FROM users WHERE username = ?",
        (username,),
    ).fetchone()

    if user and check_password_hash(user["password_hash"], password):
        payload = {
            "sub": str(user["id"]),
            "username": user["username"],
            "role": user["role"],
            "exp": datetime.utcnow() + timedelta(minutes=30),
        }

        token = jwt.encode(
            payload, current_app.config["JWT_SECRET"], algorithm="HS256"
        )

        return (
            jsonify(
                {
                    "id": user["id"],
                    "username": user["username"],
                    "token": token,
                }
            ),
            200,
        )

    return jsonify({"error": "Invalid credentials"}), 401