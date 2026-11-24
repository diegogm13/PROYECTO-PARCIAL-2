"""Backend a través de NGINX con el cliente HTTP de Playwright (APIRequestContext)."""
import pytest
from playwright.sync_api import APIRequestContext, Playwright

from conftest import ADMIN_EMAIL, ADMIN_PASSWORD, BASE_URL


@pytest.fixture(scope="module")
def api(playwright: Playwright):
    ctx = playwright.request.new_context(base_url=BASE_URL)
    yield ctx
    ctx.dispose()


@pytest.fixture(scope="module")
def token(api: APIRequestContext):
    res = api.post("/api/auth/login", data={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert res.status == 200
    return res.json()["data"]["token"]


def test_health_con_base_de_datos(api: APIRequestContext):
    res = api.get("/api/health")
    body = res.json()
    assert res.status == 200
    assert body["statusCode"] == 200
    assert body["data"]["database"] == "ok"


def test_listar_usuarios_con_token(api: APIRequestContext, token):
    res = api.get("/api/users", headers={"Authorization": f"Bearer {token}"})
    assert res.status == 200
    assert any(u["email"] == ADMIN_EMAIL for u in res.json()["data"])


def test_listar_usuarios_sin_token_401(api: APIRequestContext):
    res = api.get("/api/users")
    assert res.status == 401
    assert res.json() == {"statusCode": 401, "error": "Token requerido"}


def test_crud_completo_por_api(api: APIRequestContext, token):
    auth = {"Authorization": f"Bearer {token}"}
    created = api.post("/api/users", headers=auth,
                       data={"name": "API E2E", "email": "api-e2e@test.com", "password": "secreto123"})
    if created.status == 409:  # quedó de una ejecución anterior
        users = api.get("/api/users", headers=auth).json()["data"]
        uid = next(u["id"] for u in users if u["email"] == "api-e2e@test.com")
    else:
        assert created.status == 201
        uid = created.json()["data"]["id"]

    updated = api.put(f"/api/users/{uid}", headers=auth, data={"name": "API E2E Editado"})
    assert updated.status == 200 and updated.json()["data"]["name"] == "API E2E Editado"

    assert api.delete(f"/api/users/{uid}", headers=auth).status == 200
    assert api.get(f"/api/users/{uid}", headers=auth).status == 404


def test_frontend_servido_por_nginx(api: APIRequestContext):
    res = api.get("/")
    assert res.status == 200
    assert "Iniciar sesión" in res.text()
