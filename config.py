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

    # Crear tablas automáticamente al arrancar (dev). En producción se usan
    # migraciones (flask db upgrade), así que se desactiva.
    AUTO_CREATE_DB = True

    # Rate limiting de endpoints de autenticación (anti fuerza bruta)
    RATELIMIT_ENABLED = os.environ.get("RATELIMIT_ENABLED", "1") == "1"
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    AUTH_RATELIMIT = os.environ.get("AUTH_RATELIMIT", "20 per minute")

    # Entrega de alertas
    ALERT_WEBHOOK_TIMEOUT = int(os.environ.get("ALERT_WEBHOOK_TIMEOUT", 4))
    # Email (SMTP). Sin SMTP_HOST, los correos se registran en modo demo.
    SMTP_HOST = os.environ.get("SMTP_HOST")           # ej: smtp.gmail.com
    SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
    SMTP_USER = os.environ.get("SMTP_USER")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
    SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS", "1") == "1"
    MAIL_FROM = os.environ.get("MAIL_FROM", "alertas@socpyme.co")


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    AUTO_CREATE_DB = False   # en producción, el esquema se aplica con migraciones


class TestingConfig(Config):
    TESTING = True
    RATELIMIT_ENABLED = False   # no interferir con las pruebas


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}
