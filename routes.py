import json

from flask import Blueprint, g, jsonify, request

from auth import public_user, token_required
from db import as_json, current_driver, execute, json_param, one, query

api_bp = Blueprint("api", __name__, url_prefix="/api")

MAX_PROGRESS_BYTES = 64 * 1024


def _stamp(value):
    return value.isoformat() if hasattr(value, "isoformat") else value


def _game_or_none(slug):
    return one("SELECT slug, name FROM games WHERE slug = %s", (slug,))


def _progress_row(user_id, slug):
    row = one(
        "SELECT progress, updated_at FROM user_games WHERE user_id = %s AND game_slug = %s",
        (user_id, slug),
    )
    if not row:
        return None
    return {"progress": as_json(row["progress"], {}), "updated_at": row["updated_at"]}


@api_bp.get("/games")
def list_games():
    rows = query("SELECT slug, name FROM games ORDER BY name")
    return jsonify(games=[{"slug": r["slug"], "name": r["name"]} for r in rows])


@api_bp.get("/me")
@token_required
def me():
    return jsonify(user=public_user(dict(g.user)))


@api_bp.get("/me/games/<slug>/progress")
@token_required
def get_progress(slug):
    if not _game_or_none(slug):
        return jsonify(error="unknown_game"), 404
    row = _progress_row(g.user["id"], slug)
    return jsonify(
        game=slug,
        progress=row["progress"] if row else {},
        updated_at=_stamp(row["updated_at"]) if row else None,
    )


@api_bp.put("/me/games/<slug>/progress")
@token_required
def put_progress(slug):
    if not _game_or_none(slug):
        return jsonify(error="unknown_game"), 404

    body = request.get_json(silent=True)
    incoming = body.get("progress") if isinstance(body, dict) else None
    if not isinstance(incoming, dict):
        return jsonify(error="progress_must_be_object"), 400
    if len(json.dumps(incoming).encode("utf-8")) > MAX_PROGRESS_BYTES:
        return jsonify(error="progress_too_large"), 400

    user_id = g.user["id"]
    current = _progress_row(user_id, slug)
    merged = dict(current["progress"]) if current else {}
    merged.update(incoming)

    execute(
        "INSERT INTO user_games (user_id, game_slug, progress, updated_at) "
        "VALUES (%s, %s, %s, CURRENT_TIMESTAMP) "
        "ON CONFLICT (user_id, game_slug) DO UPDATE SET "
        "progress = EXCLUDED.progress, updated_at = CURRENT_TIMESTAMP",
        (user_id, slug, json_param(merged)),
    )

    saved = _progress_row(user_id, slug)
    return jsonify(
        game=slug,
        progress=saved["progress"],
        updated_at=_stamp(saved["updated_at"]),
    )
