"""Arranca la app con waitress (servidor WSGI de producción, multiplataforma).

Uso:
    python serve.py            # escucha en 0.0.0.0:8000
    PORT=9000 python serve.py  # otro puerto
"""
import os

from waitress import serve

from wsgi import app

if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 8000))
    print(f"🚀 SOC-PYME en producción (waitress) → http://{host}:{port}")
    serve(app, host=host, port=port)
