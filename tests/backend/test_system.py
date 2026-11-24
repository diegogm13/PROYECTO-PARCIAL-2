def test_health_ok(client):
    res = client.get("/api/health")
    body = res.get_json()
    assert res.status_code == 200
    assert body["statusCode"] == 200
    assert body["data"]["status"] == "ok"
    assert body["data"]["database"] == "ok"
    assert "commit" in body["data"]


def test_ruta_inexistente_404(client):
    res = client.get("/api/no-existe")
    assert res.status_code == 404
    assert res.get_json() == {"statusCode": 404, "error": "Ruta no encontrada"}


def test_metodo_no_permitido_405(client):
    res = client.patch("/api/health")
    assert res.status_code == 405
    assert res.get_json()["error"] == "Método no permitido"


def test_demo_error_devuelve_500_controlado(client):
    res = client.get("/api/demo/error")
    assert res.status_code == 500
    assert res.get_json() == {"statusCode": 500, "error": "Error interno del servidor"}


def test_demo_error_desactivado(app, client):
    app.config["ENABLE_DEMO_ERROR"] = False
    assert client.get("/api/demo/error").status_code == 404


def test_respuesta_json_conserva_acentos(client):
    res = client.patch("/api/health")
    assert res.content_type.startswith("application/json")
    assert "Método" in res.get_data(as_text=True)  # sin escapes é
