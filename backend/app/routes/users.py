"""CRUD de usuarios (requiere token)."""
import logging

from flask import Blueprint, g, request

from ..extensions import db
from ..models import User
from ..responses import ApiError, ok
from ..security import login_required
from ..validators import validate_user

bp = Blueprint("users", __name__, url_prefix="/api/users")
log = logging.getLogger("sa.users")


def _get_or_404(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        raise ApiError("Usuario no encontrado", 404)
    return user


def _ensure_unique_email(email, exclude_id=None):
    other = User.query.filter_by(email=email).first()
    if other is not None and other.id != exclude_id:
        raise ApiError("El email ya está registrado", 409)


@bp.get("")
@login_required
def list_users():
    users = User.query.order_by(User.id).all()
    return ok([u.to_dict() for u in users])


@bp.get("/<int:user_id>")
@login_required
def get_user(user_id):
    return ok(_get_or_404(user_id).to_dict())


@bp.post("")
@login_required
def create_user():
    data = validate_user(request.get_json(silent=True))
    _ensure_unique_email(data["email"])
    user = User(
        name=data["name"],
        email=data["email"],
        role=data.get("role", "user"),
        active=data.get("active", True),
    )
    user.set_password(data["password"])
    db.session.add(user)
    db.session.commit()
    log.info("Usuario creado", extra={"event": "user_created", "user_id": user.id, "by": g.current_user.id})
    return ok(user.to_dict(), 201)


@bp.put("/<int:user_id>")
@login_required
def update_user(user_id):
    user = _get_or_404(user_id)
    data = validate_user(request.get_json(silent=True), partial=True)
    if "email" in data:
        _ensure_unique_email(data["email"], exclude_id=user.id)
    for key, value in data.items():
        if key == "password":
            user.set_password(value)
        else:
            setattr(user, key, value)
    db.session.commit()
    log.info("Usuario actualizado", extra={"event": "user_updated", "user_id": user.id, "by": g.current_user.id})
    return ok(user.to_dict())


@bp.delete("/<int:user_id>")
@login_required
def delete_user(user_id):
    user = _get_or_404(user_id)
    if user.id == g.current_user.id:
        raise ApiError("No puede eliminar su propia cuenta", 400)
    db.session.delete(user)
    db.session.commit()
    log.info("Usuario eliminado", extra={"event": "user_deleted", "user_id": user_id, "by": g.current_user.id})
    return ok({"id": user_id, "deleted": True})
