"""SOC-PYME Solutions — punto de entrada / app factory de Flask."""
import logging
import os

import click
from dotenv import load_dotenv
from flask import Flask, render_template
from flask_login import current_user

# Cargar variables de entorno desde un archivo .env si existe
load_dotenv()

from config import config_by_name
from extensions import db, login_manager, csrf, migrate, limiter


def create_app(config_name=None):
    config_name = config_name or os.environ.get("FLASK_CONFIG", "default")
    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])

    _configure_logging(app)

    # Inicializar extensiones
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    migrate.init_app(app, db)
    limiter.init_app(app)

    # Importar modelos (registra las tablas en el metadata)
    from models import Notification  # noqa: F401

    # Registrar blueprints
    from routes.main import main_bp
    from routes.auth import auth_bp
    from routes.dashboard import dashboard_bp
    from routes.events import events_bp
    from routes.incidents import incidents_bp
    from routes.alerts import alerts_bp
    from routes.apikeys import apikeys_bp
    from routes.account import account_bp
    from routes.api import api_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(events_bp)
    app.register_blueprint(incidents_bp)
    app.register_blueprint(alerts_bp)
    app.register_blueprint(apikeys_bp)
    app.register_blueprint(account_bp)
    app.register_blueprint(api_bp)

    # La API JSON se exime de CSRF (usa sesión/inyección externa, no formularios)
    csrf.exempt(api_bp)

    _register_context(app)
    _register_errors(app)
    _register_cli(app)

    # En dev/testing se crean las tablas al vuelo; en producción se usan
    # migraciones (flask db upgrade).
    if app.config.get("AUTO_CREATE_DB", True):
        with app.app_context():
            db.create_all()

    return app


def _configure_logging(app):
    level = logging.DEBUG if app.config.get("DEBUG") else logging.INFO
    if not app.logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        ))
        app.logger.addHandler(handler)
    app.logger.setLevel(level)


def _register_context(app):
    """Inyecta datos comunes en todas las plantillas (campanita de notificaciones)."""
    @app.context_processor
    def inject_globals():
        from models import Notification
        from services import notifications_query
        unread = 0
        recent_notifs = []
        if current_user.is_authenticated:
            unread_q = notifications_query(current_user).filter(Notification.read.is_(False))
            unread = unread_q.count()
            recent_notifs = unread_q.order_by(Notification.created_at.desc()).limit(8).all()
        return {
            "unread_notifications": unread,
            "recent_notifications": recent_notifs,
        }


def _register_errors(app):
    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        db.session.rollback()
        return render_template("errors/500.html"), 500

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(429)
    def too_many_requests(e):
        return render_template("errors/429.html", detail=getattr(e, "description", "")), 429


def _register_cli(app):
    @app.cli.command("simulate")
    @click.option("--interval", default=3.0, help="Segundos entre eventos.")
    @click.option("--count", default=0, help="Nº de eventos a generar (0 = infinito).")
    def simulate(interval, count):
        """Genera eventos de seguridad realistas para demostrar el tiempo real."""
        from simulator import run_simulator
        run_simulator(app, interval=interval, count=count)

    @app.cli.command("seed")
    def seed_cmd():
        """Puebla la base de datos con datos demo (equivale a `python seed.py`)."""
        from seed import seed_database
        seed_database(app)


# Instancia para `flask run` (FLASK_APP=app.py) y para gunicorn/waitress
app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
