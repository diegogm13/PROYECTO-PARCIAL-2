from conftest import ADMIN


def test_listar_usuarios_incluye_admin(client, auth):
    res = client.get("/api/users", headers=auth)
    emails = [u["email"] for u in res.get_json()["data"]]
    assert res.status_code == 200
    assert ADMIN["email"] in emails


def test_crear_usuario_201(new_user):
    res = new_user(role="admin")
    data = res.get_json()["data"]
    assert res.status_code == 201
    assert data["id"] > 0 and data["role"] == "admin" and data["active"] is True


def test_crear_usuario_email_duplicado_409(new_user):
    new_user()
    assert new_user(name="Otra").status_code == 409


def test_crear_usuario_rol_invalido_400(new_user):
    assert new_user(role="root").status_code == 400


def test_crear_usuario_active_no_booleano_400(new_user):
    assert new_user(active="si").status_code == 400


def test_obtener_usuario(client, auth, new_user):
    uid = new_user().get_json()["data"]["id"]
    res = client.get(f"/api/users/{uid}", headers=auth)
    assert res.status_code == 200
    assert res.get_json()["data"]["name"] == "Ana López"


def test_obtener_usuario_inexistente_404(client, auth):
    assert client.get("/api/users/9999", headers=auth).status_code == 404


def test_actualizar_usuario(client, auth, new_user):
    uid = new_user().get_json()["data"]["id"]
    res = client.put(f"/api/users/{uid}", json={"name": "Ana María", "role": "admin"}, headers=auth)
    data = res.get_json()["data"]
    assert res.status_code == 200
    assert data["name"] == "Ana María" and data["role"] == "admin"


def test_actualizar_password_permite_login(client, auth, new_user):
    uid = new_user().get_json()["data"]["id"]
    client.put(f"/api/users/{uid}", json={"password": "nueva123"}, headers=auth)
    res = client.post("/api/auth/login", json={"email": "ana@test.com", "password": "nueva123"})
    assert res.status_code == 200


def test_actualizar_email_duplicado_409(client, auth, new_user):
    uid = new_user().get_json()["data"]["id"]
    res = client.put(f"/api/users/{uid}", json={"email": ADMIN["email"]}, headers=auth)
    assert res.status_code == 409


def test_actualizar_mismo_email_ok(client, auth, new_user):
    uid = new_user().get_json()["data"]["id"]
    res = client.put(f"/api/users/{uid}", json={"email": "ana@test.com"}, headers=auth)
    assert res.status_code == 200


def test_actualizar_cuerpo_vacio_400(client, auth, new_user):
    uid = new_user().get_json()["data"]["id"]
    assert client.put(f"/api/users/{uid}", json={}, headers=auth).status_code == 400


def test_actualizar_campo_extra_400(client, auth, new_user):
    uid = new_user().get_json()["data"]["id"]
    assert client.put(f"/api/users/{uid}", json={"id": 5}, headers=auth).status_code == 400


def test_actualizar_inexistente_404(client, auth):
    assert client.put("/api/users/9999", json={"name": "X Y"}, headers=auth).status_code == 404


def test_eliminar_usuario(client, auth, new_user):
    uid = new_user().get_json()["data"]["id"]
    res = client.delete(f"/api/users/{uid}", headers=auth)
    assert res.status_code == 200
    assert res.get_json()["data"] == {"id": uid, "deleted": True}
    assert client.get(f"/api/users/{uid}", headers=auth).status_code == 404


def test_eliminar_inexistente_404(client, auth):
    assert client.delete("/api/users/9999", headers=auth).status_code == 404


def test_no_puede_eliminarse_a_si_mismo_400(client, auth):
    me = client.get("/api/auth/me", headers=auth).get_json()["data"]
    assert client.delete(f"/api/users/{me['id']}", headers=auth).status_code == 400


def test_usuario_eliminado_pierde_acceso(client, auth, new_user):
    uid = new_user().get_json()["data"]["id"]
    token = client.post("/api/auth/login",
                        json={"email": "ana@test.com", "password": "secreto1"}).get_json()["data"]["token"]
    client.delete(f"/api/users/{uid}", headers=auth)
    res = client.get("/api/users", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401
