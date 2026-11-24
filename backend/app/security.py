"""JWT: emisión, verificación y decorador de rutas protegidas."""
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import current_app, g, request

from .extensions import db
from .models import User
from .responses import ApiError


def create_token(user):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role,
        "iat": now,
        "exp": now + timedelta(minutes=current_app.config["JWT_EXPIRES_MINUTES"]),
    }
    return jwt.encode(payload, current_app.config["JWT_SECRET"], algorithm="HS256")


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            raise ApiError("Token requerido", 401)
        try:
            payload = jwt.decode(header[7:], current_app.config["JWT_SECRET"], algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            raise ApiError("El token expiró", 401)
        except jwt.InvalidTokenError:
            raise ApiError("Token inválido", 401)
        user = db.session.get(User, int(payload["sub"]))
        if user is None or not user.active:
            raise ApiError("Usuario no autorizado", 401)
        g.current_user = user
        return view(*args, **kwargs)

    return wrapper
