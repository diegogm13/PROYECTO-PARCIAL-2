import pytest

from app import create_app
from app.extensions import db

ADMIN = {"email": "admin@test.com", "password": "Admin123!"}


@pytest.fixture
def app(tmp_path):
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'test.db'}",
        "ADMIN_EMAIL": ADMIN["email"],
        "ADMIN_PASSWORD": ADMIN["password"],
        "JWT_SECRET": "secreto-de-pruebas-con-longitud-suficiente-123",
    })
    yield app
    with app.app_context():
        db.session.remove()
        db.engine.dispose()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def token(client):
    res = client.post("/api/auth/login", json=ADMIN)
    return res.get_json()["data"]["token"]


@pytest.fixture
def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def new_user(client, auth):
    def _create(**overrides):
        body = {"name": "Ana López", "email": "ana@test.com", "password": "secreto1"}
        body.update(overrides)
        return client.post("/api/users", json=body, headers=auth)
    return _create
