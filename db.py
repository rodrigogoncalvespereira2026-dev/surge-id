import json
import os
import sqlite3
import uuid
from pathlib import Path

from flask import current_app, g

SCHEMA_FILE = Path(__file__).with_name("schema.sql")
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
SURGE_PREFIX = "SG-"


def new_id():
    return uuid.uuid4().hex


def driver_for(url):
    return "sqlite" if url.startswith(("sqlite:", "sqlite3:", "file:")) else "postgres"


def current_driver():
    return driver_for(current_app.config["DATABASE_URL"])


def json_param(value):
    if current_driver() == "postgres":
        from psycopg.types.json import Jsonb

        return Jsonb(value)
    return json.dumps(value)


def connect(url):
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if driver_for(url) == "sqlite":
        path = url.split("///", 1)[-1] if "///" in url else ":memory:"
        if path == ":memory:" or not os.path.isabs(path):
            path = os.path.abspath(path)
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
    from psycopg.rows import dict_row
    import psycopg

    return psycopg.connect(url, row_factory=dict_row)


def _prepare(sql):
    if current_driver() == "sqlite":
        return sql.replace("%s", "?")
    return sql


def get_db():
    conn = g.get("db")
    if conn is None:
        conn = connect(current_app.config["DATABASE_URL"])
        g.db = conn
    return conn


def close_db(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass


def query(sql, params=()):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(_prepare(sql), params)
    rows = cur.fetchall()
    cur.close()
    return [dict(row) for row in rows]


def one(sql, params=()):
    rows = query(sql, params)
    return rows[0] if rows else None


def execute(sql, params=()):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(_prepare(sql), params)
    conn.commit()
    cur.close()


def as_json(value, default=None):
    fallback = {} if default is None else default
    if value is None:
        return fallback
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8")
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return fallback
    return fallback


def init_db():
    script = SCHEMA_FILE.read_text(encoding="utf-8")
    conn = get_db()
    if current_driver() == "sqlite":
        conn.executescript(script)
    else:
        conn.execute(script)
    conn.commit()


def random_surge_id():
    import random

    body = "".join(random.choice(ALPHABET) for _ in range(6))
    return SURGE_PREFIX + body


def unique_surge_id(tries=12):
    for _ in range(tries):
        candidate = random_surge_id()
        if not one("SELECT id FROM users WHERE surge_id = %s", (candidate,)):
            return candidate
    raise RuntimeError("Não foi possível gerar um Surge ID único")
