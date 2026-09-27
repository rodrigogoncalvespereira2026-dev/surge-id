import re
import time
from functools import wraps

import bcrypt
import jwt
from flask import Blueprint, current_app, g, jsonify, request

from db import execute, new_id, one, unique_surge_id
from rate_limit import limiter

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD = 8


def create_token(user_id):
    now = int(time.time())
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + current_app.config["JWT_EXP_DAYS"] * 86400,
    }
    return jwt.encode(payload, current_app.config["JWT_SECRET"], algorithm="HS256")


def decode_token(token):
    return jwt.decode(token, current_app.config["JWT_SECRET"], algorithms=["HS256"])


def public_user(row):
    created = row.get("created_at")
    return {
        "id": row["id"],
        "email": row["email"],
        "surge_id": row["surge_id"],
        "display_name": row["display_name"],
        "created_at": created.isoformat() if hasattr(created, "isoformat") else created,
    }


def hash_password(password):
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def check_password(password, password_hash):
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def token_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return jsonify(error="missing_token"), 401
        try:
            payload = decode_token(header[7:].strip())
        except jwt.ExpiredSignatureError:
            return jsonify(error="expired_token"), 401
        except jwt.InvalidTokenError:
            return jsonify(error="invalid_token"), 401
        user = one(
            "SELECT id, email, surge_id, display_name, created_at FROM users WHERE id = %s",
            (payload.get("sub"),),
        )
        if not user:
            return jsonify(error="unknown_user"), 401
        g.user = user
        return fn(*args, **kwargs)

    return wrapper


@auth_bp.post("/register")
@limiter.limit(lambda: current_app.config["RATELIMIT_AUTH"])
def register():
    body = request.get_json(silent=True) or {}
    email = str(body.get("email", "")).strip().lower()
    password = str(body.get("password", ""))
    display_name = str(body.get("display_name") or "").strip()[:40]

    if not EMAIL_RE.match(email) or len(email) > 254:
        return jsonify(error="invalid_email"), 400
    if len(password) < MIN_PASSWORD:
        return jsonify(error="weak_password"), 400
    if one("SELECT id FROM users WHERE LOWER(email) = LOWER(%s)", (email,)):
        return jsonify(error="email_taken"), 409

    user_id = new_id()
    surge_id = unique_surge_id()
    execute(
        "INSERT INTO users (id, email, password_hash, surge_id, display_name) "
        "VALUES (%s, %s, %s, %s, %s)",
        (user_id, email, hash_password(password), surge_id, display_name or None),
    )
    user = one(
        "SELECT id, email, surge_id, display_name, created_at FROM users WHERE id = %s",
        (user_id,),
    )
    return jsonify(token=create_token(user_id), user=public_user(user)), 201


@auth_bp.post("/login")
@limiter.limit(lambda: current_app.config["RATELIMIT_AUTH"])
def login():
    body = request.get_json(silent=True) or {}
    email = str(body.get("email", "")).strip().lower()
    password = str(body.get("password", ""))

    user = one(
        "SELECT id, email, password_hash, surge_id, display_name, created_at "
        "FROM users WHERE LOWER(email) = LOWER(%s)",
        (email,),
    )
    if not user or not check_password(password, user["password_hash"]):
        return jsonify(error="invalid_credentials"), 401

    return jsonify(token=create_token(user["id"]), user=public_user(user)), 200
