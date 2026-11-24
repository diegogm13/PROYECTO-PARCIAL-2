"""Configuración leída de variables de entorno (nunca se suben secretos al repo)."""
import os


class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///sa_local.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-solo-para-desarrollo-local-cambiar")
    JWT_EXPIRES_MINUTES = int(os.getenv("JWT_EXPIRES_MINUTES", "120"))

    # Usuario administrador que se crea al arrancar si no existe
    ADMIN_NAME = os.getenv("ADMIN_NAME", "Administrador")
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@sa.com").lower()
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Admin123!")

    APP_VERSION = os.getenv("APP_VERSION", "2.0.0")
    GIT_SHA = os.getenv("GIT_SHA", "local")
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

    # Endpoint de demostración que lanza una excepción (para ver errores en OpenObserve)
    ENABLE_DEMO_ERROR = os.getenv("ENABLE_DEMO_ERROR", "1") == "1"
