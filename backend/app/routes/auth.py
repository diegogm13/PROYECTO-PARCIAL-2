"""Login y Register."""
import logging

from flask import Blueprint, g, request

from ..extensions import db
from ..models import User
from ..responses import ApiError, ok
from ..security import create_token, login_required
from ..validators import require_json, validate_user

bp = Blueprint("auth", __name__, url_prefix="/api/auth")
log = logging.getLogger("sa.auth")


@bp.post("/register")
def register():
    data = validate_user(request.get_json(silent=True), allowed=("name", "email", "password"))
    if User.query.filter_by(email=data["email"]).first():
        raise ApiError("El email ya está registrado", 409)
    user = User(name=data["name"], email=data["email"], role="user")
    user.set_password(data["password"])
    db.session.add(user)
    db.session.commit()
    log.info("Usuario registrado", extra={"event": "user_registered", "user_id": user.id})
    return ok(user.to_dict(), 201)


@bp.post("/login")
def login():
    payload = require_json(request.get_json(silent=True))
    email = str(payload.get("email", "")).strip().lower()
    password = payload.get("password", "")
    if not email or not password:
        raise ApiError("Email y contraseña son obligatorios", 400)
    user = User.query.filter_by(email=email).first()
    if user is None or not user.check_password(password):
        log.warning("Intento de login fallido", extra={"event": "login_failed", "email": email})
        raise ApiError("Credenciales inválidas", 401)
    if not user.active:
        raise ApiError("La cuenta está desactivada", 403)
    log.info("Login exitoso", extra={"event": "login_ok", "user_id": user.id})
    return ok({"token": create_token(user), "user": user.to_dict()})


@bp.get("/me")
@login_required
def me():
    return ok(g.current_user.to_dict())
