"""Punto de entrada WSGI para servidores de producción (waitress/gunicorn).

Ejemplos:
    waitress-serve --listen=0.0.0.0:8000 wsgi:app      # Windows / multiplataforma
    gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app             # Linux
"""
import os

# Por defecto, producción (a menos que se defina FLASK_CONFIG explícitamente)
os.environ.setdefault("FLASK_CONFIG", "production")

from app import create_app

app = create_app()
