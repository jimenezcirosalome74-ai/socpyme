"""Autenticación: registro, login y logout."""
from flask import (
    Blueprint, render_template, redirect, url_for, flash, request,
)
from flask_login import login_user, logout_user, login_required, current_user

from extensions import db
from models import User, Company
from forms import RegisterForm, LoginForm, ForgotPasswordForm, ResetPasswordForm
from services import generate_reset_token, verify_reset_token

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

        # Modelo SaaS de autoservicio: cada registro crea su propia empresa
        # y el usuario queda como administrador de ella.
        company = Company(name=form.company.data.strip(), kind="cliente")
        db.session.add(company)
        db.session.flush()  # obtener company.id

        user = User(
            name=form.name.data.strip(),
            email=email,
            role="admin",
            company_id=company.id,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()

        login_user(user)
        flash(f"¡Bienvenido, {user.name}! Tu empresa «{company.name}» fue creada.", "success")
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


@auth_bp.route("/recuperar", methods=["GET", "POST"])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    form = ForgotPasswordForm()
    reset_link = None
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user = User.query.filter_by(email=email).first()
        # No revelamos si el email existe o no (evita enumeración de cuentas)
        if user:
            token = generate_reset_token(user)
            reset_link = url_for("auth.reset_password", token=token, _external=True)
        flash("Si el email está registrado, te enviamos un enlace para restablecer la contraseña.", "info")
        # Sin servicio de correo aún: mostramos el enlace en pantalla (entorno demo)
        return render_template("auth/forgot.html", form=form, reset_link=reset_link)

    return render_template("auth/forgot.html", form=form, reset_link=None)


@auth_bp.route("/restablecer/<token>", methods=["GET", "POST"])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    user = verify_reset_token(token)
    if user is None:
        flash("El enlace de recuperación es inválido o expiró.", "error")
        return redirect(url_for("auth.forgot_password"))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash("Tu contraseña fue restablecida. Ya podés ingresar.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset.html", form=form, token=token)
