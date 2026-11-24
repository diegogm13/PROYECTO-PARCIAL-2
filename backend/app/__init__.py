"""Fábrica de la aplicación Flask."""
import logging

from flask import Flask
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import HTTPException

from .config import Config
from .extensions import db
from .logging_config import setup_logging
from .models import User
from .responses import ApiError, fail
from .routes import ALL_BLUEPRINTS
from .telemetry import init_telemetry, register_request_hooks

log = logging.getLogger("sa.app")

HTTP_MESSAGES = {404: "Ruta no encontrada", 405: "Método no permitido"}


def create_app(overrides=None):
    setup_logging()
    app = Flask(__name__)
    app.config.from_object(Config)
    if overrides:
        app.config.update(overrides)
    app.json.ensure_ascii = False
    app.json.sort_keys = False

    db.init_app(app)
    for bp in ALL_BLUEPRINTS:
        app.register_blueprint(bp)
    register_request_hooks(app)
    _register_error_handlers(app)

    with app.app_context():
        db.create_all()
        _seed_admin(app)
        if not app.config.get("TESTING"):
            init_telemetry(app, db.engine)

    return app


def _seed_admin(app):
    cfg = app.config
    if User.query.filter_by(email=cfg["ADMIN_EMAIL"]).first():
        return
    admin = User(name=cfg["ADMIN_NAME"], email=cfg["ADMIN_EMAIL"], role="admin")
    admin.set_password(cfg["ADMIN_PASSWORD"])
    db.session.add(admin)
    try:
        db.session.commit()
        log.info("Usuario administrador creado", extra={"event": "admin_seeded"})
    except IntegrityError:  # otro proceso lo creó primero
        db.session.rollback()


def _register_error_handlers(app):
    @app.errorhandler(ApiError)
    def api_error(e):
        return fail(e.message, e.status)

    @app.errorhandler(HTTPException)
    def http_error(e):
        return fail(HTTP_MESSAGES.get(e.code, e.name), e.code)

    @app.errorhandler(Exception)
    def unhandled(e):
        db.session.rollback()
        log.exception("Excepción no controlada", extra={"event": "unhandled_exception",
                                                        "exception_type": type(e).__name__})
        return fail("Error interno del servidor", 500)
