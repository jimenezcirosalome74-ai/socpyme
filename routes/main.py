"""Rutas públicas: landing y páginas informativas."""
from flask import Blueprint, render_template, redirect, url_for
from flask_login import current_user

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    # Si ya inició sesión, mostrar igual la landing (con CTA hacia el panel)
    return render_template("index.html")


@main_bp.route("/demo")
def demo():
    """Atajo directo al login con las credenciales demo visibles."""
    return redirect(url_for("auth.login", demo=1))
