"""Autenticación: registro, login y logout."""
from flask import (
    Blueprint, render_template, redirect, url_for, flash, request,
)
from flask_login import login_user, logout_user, login_required, current_user

from extensions import db
from models import User
from forms import RegisterForm, LoginForm

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/registro", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    form = RegisterForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        if User.query.filter_by(email=email).first():
            flash("Ya existe una cuenta con ese email.", "error")
            return render_template("auth/register.html", form=form)

        user = User(
            name=form.name.data.strip(),
            company=form.company.data.strip(),
            email=email,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()

        login_user(user)
        flash(f"¡Bienvenido, {user.name}! Tu cuenta fue creada.", "success")
        return redirect(url_for("dashboard.index"))

    return render_template("auth/register.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)
            flash(f"Sesión iniciada. ¡Hola, {user.name}!", "success")
            next_page = request.args.get("next")
            # Evitar open-redirect: solo rutas internas
            if not next_page or not next_page.startswith("/"):
                next_page = url_for("dashboard.index")
            return redirect(next_page)
        flash("Email o contraseña incorrectos.", "error")

    show_demo = request.args.get("demo") == "1"
    return render_template("auth/login.html", form=form, show_demo=show_demo)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Cerraste sesión correctamente.", "success")
    return redirect(url_for("main.index"))
