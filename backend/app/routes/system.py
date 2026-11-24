"""Salud del servicio y endpoint de demostración de errores."""
from flask import Blueprint, current_app
from sqlalchemy import text

from ..extensions import db
from ..responses import ApiError, ok

bp = Blueprint("system", __name__, url_prefix="/api")


@bp.get("/health")
def health():
    try:
        db.session.execute(text("SELECT 1"))
        database = "ok"
    except Exception:  # noqa: BLE001 - se informa el estado, no se propaga
        database = "error"
    cfg = current_app.config
    return ok({
        "status": "ok" if database == "ok" else "degraded",
        "database": database,
        "version": cfg["APP_VERSION"],
        "commit": cfg["GIT_SHA"],
        "environment": cfg["ENVIRONMENT"],
    })


@bp.get("/demo/error")
def demo_error():
    """Lanza una excepción a propósito: sirve para ver logs de error y tasa 5xx en OpenObserve."""
    if not current_app.config["ENABLE_DEMO_ERROR"]:
        raise ApiError("Ruta no encontrada", 404)
    raise RuntimeError("Excepción de demostración para observabilidad")
