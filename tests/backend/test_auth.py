import jwt
import pytest

from conftest import ADMIN


# ---------------------------- Register ----------------------------
def test_register_ok(client):
    res = client.post("/api/auth/register",
                      json={"name": "Luis", "email": "LUIS@Test.com", "password": "secreto1"})
    body = res.get_json()
    assert res.status_code == 201
    assert body["data"]["email"] == "luis@test.com"
    assert body["data"]["role"] == "user"
    assert "password" not in body["data"] and "password_hash" not in body["data"]


def test_register_email_duplicado_409(client):
    client.post("/api/auth/register", json={"name": "Luis", "email": "l@t.com", "password": "secreto1"})
    res = client.post("/api/auth/register", json={"name": "Otro", "email": "l@t.com", "password": "secreto1"})
    assert res.status_code == 409


@pytest.mark.parametrize("body, mensaje", [
    ({"email": "a@t.com", "password": "secreto1"}, "obligatorios"),
    ({"name": "Luis", "email": "no-es-email", "password": "secreto1"}, "email"),
    ({"name": "Luis", "email": "a@t.com", "password": "123"}, "contraseña"),
    ({"name": "L", "email": "a@t.com", "password": "secreto1"}, "nombre"),
    ({"name": "Luis", "email": "a@t.com", "password": "secreto1", "role": "admin"}, "no permitidos"),
])
def test_register_validaciones_400(client, body, mensaje):
    res = client.post("/api/auth/register", json=body)
    assert res.status_code == 400
    assert mensaje in res.get_json()["error"]


def test_register_sin_json_400(client):
    res = client.post("/api/auth/register", data="texto", content_type="text/plain")
    assert res.status_code == 400


# ----------------------------- Login ------------------------------
def test_login_ok_devuelve_token(client, app):
    res = client.post("/api/auth/login", json=ADMIN)
    data = res.get_json()["data"]
    assert res.status_code == 200
    assert data["user"]["role"] == "admin"
    payload = jwt.decode(data["token"], app.config["JWT_SECRET"], algorithms=["HS256"])
    assert payload["email"] == ADMIN["email"]


def test_login_password_incorrecto_401(client):
    res = client.post("/api/auth/login", json={"email": ADMIN["email"], "password": "malo123"})
    assert res.status_code == 401
    assert res.get_json()["error"] == "Credenciales inválidas"


def test_login_usuario_inexistente_401(client):
    res = client.post("/api/auth/login", json={"email": "nadie@t.com", "password": "secreto1"})
    assert res.status_code == 401


def test_login_campos_vacios_400(client):
    assert client.post("/api/auth/login", json={}).status_code == 400


def test_login_usuario_inactivo_403(client, new_user, auth):
    uid = new_user(active=False).get_json()["data"]["id"]
    assert uid
    res = client.post("/api/auth/login", json={"email": "ana@test.com", "password": "secreto1"})
    assert res.status_code == 403


def test_register_y_luego_login(client):
    client.post("/api/auth/register", json={"name": "Eva", "email": "eva@t.com", "password": "secreto1"})
    res = client.post("/api/auth/login", json={"email": "eva@t.com", "password": "secreto1"})
    assert res.status_code == 200


# ------------------------------ Token -----------------------------
def test_me_con_token(client, auth):
    res = client.get("/api/auth/me", headers=auth)
    assert res.status_code == 200
    assert res.get_json()["data"]["email"] == ADMIN["email"]


@pytest.mark.parametrize("header", [None, "Bearer token-falso", "Basic abc"])
def test_rutas_protegidas_sin_token_valido_401(client, header):
    headers = {"Authorization": header} if header else {}
    assert client.get("/api/users", headers=headers).status_code == 401


def test_token_expirado_401(client, app):
    app.config["JWT_EXPIRES_MINUTES"] = -1
    token = client.post("/api/auth/login", json=ADMIN).get_json()["data"]["token"]
    res = client.get("/api/users", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401
    assert res.get_json()["error"] == "El token expiró"
