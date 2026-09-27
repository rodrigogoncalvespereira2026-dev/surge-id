import os

import pytest

from app import create_app
from db import execute


def _db_url(tmp_path):
    return os.environ.get("TEST_DATABASE_URL") or "sqlite:///{}".format(
        tmp_path / "test.db"
    )


@pytest.fixture()
def app(tmp_path):
    application = create_app(
        {
            "TESTING": True,
            "DATABASE_URL": _db_url(tmp_path),
            "JWT_SECRET": "segredo-de-teste-com-mais-de-32-bytes!",
            "AUTO_INIT_DB": True,
            "RATELIMIT_ENABLED": False,
        }
    )
    with application.app_context():
        execute("DELETE FROM user_games")
        execute("DELETE FROM users")
    yield application


@pytest.fixture()
def client(app):
    return app.test_client()


def register(client, email="ranger@power.rangers", password="morphing123", **extra):
    body = {"email": email, "password": password}
    body.update(extra)
    return client.post("/api/auth/register", json=body)


def auth_header(token):
    return {"Authorization": "Bearer " + token}


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.get_json()["status"] == "ok"


def test_register_returns_token_and_surge_id(client):
    res = register(client)
    assert res.status_code == 201
    data = res.get_json()
    assert data["token"]
    surge_id = data["user"]["surge_id"]
    assert surge_id.startswith("SG-")
    assert len(surge_id) == 9
    assert data["user"]["email"] == "ranger@power.rangers"


def test_register_rejects_duplicate_email(client):
    register(client)
    res = register(client)
    assert res.status_code == 409
    assert res.get_json()["error"] == "email_taken"


def test_register_is_case_insensitive(client):
    register(client, email="Ranger@Power.Rangers")
    res = register(client, email="ranger@power.rangers")
    assert res.status_code == 409


def test_register_validates_email_and_password(client):
    assert register(client, email="sem-arroba").status_code == 400
    assert register(client, password="curto").status_code == 400


def test_login_success_and_failures(client):
    register(client, password="morphing123")
    ok = client.post(
        "/api/auth/login", json={"email": "RANGER@power.rangers", "password": "morphing123"}
    )
    assert ok.status_code == 200
    assert ok.get_json()["token"]

    wrong = client.post(
        "/api/auth/login", json={"email": "ranger@power.rangers", "password": "errada123"}
    )
    assert wrong.status_code == 401

    unknown = client.post(
        "/api/auth/login", json={"email": "ninguem@power.rangers", "password": "morphing123"}
    )
    assert unknown.status_code == 401


def test_me_requires_token(client):
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/me", headers=auth_header("token-invalido")).status_code == 401

    token = register(client).get_json()["token"]
    res = client.get("/api/me", headers=auth_header(token))
    assert res.status_code == 200
    assert res.get_json()["user"]["email"] == "ranger@power.rangers"


def test_games_list_includes_primal_force(client):
    res = client.get("/api/games")
    assert res.status_code == 200
    slugs = [game["slug"] for game in res.get_json()["games"]]
    assert "primal_force" in slugs


def test_progress_create_merge_and_read(client):
    token = register(client).get_json()["token"]
    headers = auth_header(token)

    first = client.put(
        "/api/me/games/primal_force/progress",
        json={"progress": {"moedas": 100, "nivel": 3}},
        headers=headers,
    )
    assert first.status_code == 200
    assert first.get_json()["progress"] == {"moedas": 100, "nivel": 3}

    second = client.put(
        "/api/me/games/primal_force/progress",
        json={"progress": {"moedas": 250, "trofeus": 12}},
        headers=headers,
    )
    assert second.status_code == 200
    assert second.get_json()["progress"] == {"moedas": 250, "nivel": 3, "trofeus": 12}

    read = client.get("/api/me/games/primal_force/progress", headers=headers)
    assert read.status_code == 200
    assert read.get_json()["progress"] == {"moedas": 250, "nivel": 3, "trofeus": 12}
    assert read.get_json()["updated_at"]


def test_progress_requires_auth_and_valid_game(client):
    assert client.put("/api/me/games/primal_force/progress", json={"progress": {}}).status_code == 401

    token = register(client).get_json()["token"]
    headers = auth_header(token)
    assert (
        client.get("/api/me/games/nao_existe/progress", headers=headers).status_code == 404
    )
    assert (
        client.put("/api/me/games/nao_existe/progress", json={"progress": {}}, headers=headers).status_code
        == 404
    )


def test_progress_rejects_invalid_payload(client):
    token = register(client).get_json()["token"]
    headers = auth_header(token)
    assert (
        client.put("/api/me/games/primal_force/progress", json={"progress": 42}, headers=headers).status_code
        == 400
    )
    assert (
        client.put("/api/me/games/primal_force/progress", json={"nope": 1}, headers=headers).status_code
        == 400
    )


def test_progress_is_isolated_per_user(client):
    first = register(client, email="um@power.rangers").get_json()["token"]
    second = register(client, email="dois@power.rangers").get_json()["token"]

    client.put(
        "/api/me/games/primal_force/progress",
        json={"progress": {"moedas": 111}},
        headers=auth_header(first),
    )
    other = client.get("/api/me/games/primal_force/progress", headers=auth_header(second))
    assert other.status_code == 200
    assert other.get_json()["progress"] == {}
