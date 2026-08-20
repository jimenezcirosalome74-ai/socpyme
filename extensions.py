"""Extensiones Flask instanciadas una sola vez y compartidas por la app factory."""
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf import CSRFProtect
from flask_migrate import Migrate
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
migrate = Migrate()
limiter = Limiter(key_func=get_remote_address, default_limits=[])

# Configuración del login
login_manager.login_view = "auth.login"
login_manager.login_message = "Por favor iniciá sesión para acceder al panel."
login_manager.login_message_category = "warning"
