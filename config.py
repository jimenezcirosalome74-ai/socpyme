"""Configuración de la aplicación SOC-PYME Solutions."""
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    """Configuración base."""
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-cambia-esto-en-produccion-2026")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///" + os.path.join(BASE_DIR, "socpyme.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Seguridad de sesiones / cookies
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # En producción (HTTPS) poner True vía env var
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"

    # CSRF (Flask-WTF)
    WTF_CSRF_TIME_LIMIT = None  # el token vive lo que dure la sesión

    # Parámetros de negocio
    ALERT_DEFAULT_WINDOW_MIN = 5      # ventana por defecto de las reglas de alerta
    ALERT_DEFAULT_THRESHOLD = 3       # nº de eventos críticos para disparar alerta
    EVENTS_PER_PAGE = 15              # paginación de la lista de eventos


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
