"""Validación de los cuerpos JSON de usuarios."""
import re

from .responses import ApiError

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ROLES = ("admin", "user")
MIN_PASSWORD = 6


def _name(value):
    if not isinstance(value, str) or not 2 <= len(value.strip()) <= 100:
        raise ApiError("El nombre debe tener entre 2 y 100 caracteres", 400)
    return value.strip()


def _email(value):
    if not isinstance(value, str) or not EMAIL_RE.match(value.strip()):
        raise ApiError("El email no tiene un formato válido", 400)
    return value.strip().lower()


def _password(value):
    if not isinstance(value, str) or len(value) < MIN_PASSWORD:
        raise ApiError(f"La contraseña debe tener al menos {MIN_PASSWORD} caracteres", 400)
    return value


def _role(value):
    if value not in ROLES:
        raise ApiError("El rol debe ser 'admin' o 'user'", 400)
    return value


def _active(value):
    if not isinstance(value, bool):
        raise ApiError("El campo 'active' debe ser booleano", 400)
    return value


FIELDS = {"name": _name, "email": _email, "password": _password, "role": _role, "active": _active}


def require_json(payload):
    if not isinstance(payload, dict):
        raise ApiError("Se esperaba un cuerpo JSON (objeto)", 400)
    return payload


def validate_user(payload, *, partial=False, allowed=tuple(FIELDS), required=("name", "email", "password")):
    """Valida y normaliza. partial=True (PUT) permite enviar solo algunos campos."""
    payload = require_json(payload)
    extra = set(payload) - set(allowed)
    if extra:
        raise ApiError(f"Campos no permitidos: {', '.join(sorted(extra))}", 400)
    if partial:
        if not payload:
            raise ApiError("Debe enviar al menos un campo para actualizar", 400)
    else:
        missing = [f for f in required if f not in payload]
        if missing:
            raise ApiError(f"Campos obligatorios: {', '.join(missing)}", 400)
    return {key: FIELDS[key](value) for key, value in payload.items()}
