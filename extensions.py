"""Extensiones Flask instanciadas una sola vez y compartidas por la app factory."""
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf import CSRFProtect

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()

# Configuración del login
login_manager.login_view = "auth.login"
login_manager.login_message = "Por favor iniciá sesión para acceder al panel."
login_manager.login_message_category = "warning"
