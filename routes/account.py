"""Gestión de cuenta: perfil, contraseña, empresa y usuarios de la empresa."""
from functools import wraps

from flask import (
    Blueprint, render_template, redirect, url_for, flash, abort, request, session,
)
from flask_login import login_required, current_user, logout_user

from extensions import db
from models import User, Company
from forms import ProfileForm, CompanyForm, ChangePasswordForm, InviteUserForm
from services import log_audit, generate_temp_password

account_bp = Blueprint("account", __name__, url_prefix="/cuenta")


def admin_required(view):
    """Solo administradores de empresa (o analista) pueden gestionar usuarios."""
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if current_user.role not in ("admin", "analista"):
            abort(403)
        return view(*args, **kwargs)
    return wrapped


@account_bp.route("/")
@login_required
def index():
    profile_form = ProfileForm(obj=current_user)
    company_form = CompanyForm(company_name=current_user.company_name)
    password_form = ChangePasswordForm()
    return render_template(
        "account/index.html",
        profile_form=profile_form,
        company_form=company_form,
        password_form=password_form,
    )


@account_bp.route("/perfil", methods=["POST"])
@login_required
def update_profile():
    form = ProfileForm()
    if not form.validate_on_submit():
        for errs in form.errors.values():
            for e in errs:
                flash(e, "error")
        return redirect(url_for("account.index"))

    email = form.email.data.strip().lower()
    other = User.query.filter(User.email == email, User.id != current_user.id).first()
    if other:
        flash("Ese email ya está en uso por otra cuenta.", "error")
        return redirect(url_for("account.index"))

    current_user.name = form.name.data.strip()
    current_user.email = email
    db.session.commit()
    flash("Perfil actualizado.", "success")
    return redirect(url_for("account.index"))


@account_bp.route("/empresa", methods=["POST"])
@login_required
def update_company():
    if current_user.role not in ("admin", "analista"):
        abort(403)
    form = CompanyForm()
    if not form.validate_on_submit() or current_user.company is None:
        flash("No se pudo actualizar la empresa.", "error")
        return redirect(url_for("account.index"))
    old = current_user.company.name
    current_user.company.name = form.company_name.data.strip()
    log_audit("company", current_user.company_id, "renombrada",
              f"«{old}» → «{current_user.company.name}».",
              current_user, company_id=current_user.company_id)
    db.session.commit()
    flash("Nombre de la empresa actualizado.", "success")
    return redirect(url_for("account.index"))


@account_bp.route("/password", methods=["POST"])
@login_required
def change_password():
    form = ChangePasswordForm()
    if not form.validate_on_submit():
        for errs in form.errors.values():
            for e in errs:
                flash(e, "error")
        return redirect(url_for("account.index"))

    if not current_user.check_password(form.current_password.data):
        flash("La contraseña actual es incorrecta.", "error")
        return redirect(url_for("account.index"))

    current_user.set_password(form.password.data)
    db.session.commit()
    flash("Contraseña actualizada correctamente.", "success")
    return redirect(url_for("account.index"))


# ---------------------------------------------------------------------------
# Usuarios de la empresa (solo admin)
# ---------------------------------------------------------------------------
@account_bp.route("/usuarios", methods=["GET"])
@admin_required
def users():
    form = InviteUserForm()
    members = (
        User.query.filter_by(company_id=current_user.company_id)
        .order_by(User.name).all()
    )
    temp = session.pop("invited_temp_password", None)
    return render_template("account/users.html", users=members, form=form, temp=temp)


@account_bp.route("/usuarios/invitar", methods=["POST"])
@admin_required
def invite_user():
    form = InviteUserForm()
    if not form.validate_on_submit():
        for errs in form.errors.values():
            for e in errs:
                flash(e, "error")
        return redirect(url_for("account.users"))

    email = form.email.data.strip().lower()
    if User.query.filter_by(email=email).first():
        flash("Ya existe una cuenta con ese email.", "error")
        return redirect(url_for("account.users"))

    temp_password = generate_temp_password()
    user = User(
        name=form.name.data.strip(),
        email=email,
        role=form.role.data,
        company_id=current_user.company_id,
    )
    user.set_password(temp_password)
    db.session.add(user)
    db.session.flush()
    log_audit("user", user.id, "invitado",
              f"{user.name} ({user.role}) agregado a la empresa.",
              current_user, company_id=current_user.company_id)
    db.session.commit()

    # La contraseña temporal se muestra una sola vez (no hay envío de email todavía)
    session["invited_temp_password"] = {"email": email, "password": temp_password}
    flash(f"Usuario «{user.name}» creado. Compartile la contraseña temporal.", "success")
    return redirect(url_for("account.users"))


def _get_member(user_id):
    user = db.session.get(User, user_id)
    if user is None or user.company_id != current_user.company_id:
        abort(404)
    return user


@account_bp.route("/usuarios/<int:user_id>/rol", methods=["POST"])
@admin_required
def change_role(user_id):
    user = _get_member(user_id)
    if user.id == current_user.id:
        flash("No podés cambiar tu propio rol.", "error")
        return redirect(url_for("account.users"))
    new_role = request.form.get("role", "")
    if new_role not in ("cliente", "admin"):
        flash("Rol inválido.", "error")
        return redirect(url_for("account.users"))
    user.role = new_role
    log_audit("user", user.id, "rol", f"{user.name} → {user.role_label}.",
              current_user, company_id=current_user.company_id)
    db.session.commit()
    flash(f"Rol de «{user.name}» actualizado a {user.role_label}.", "success")
    return redirect(url_for("account.users"))


@account_bp.route("/usuarios/<int:user_id>/eliminar", methods=["POST"])
@admin_required
def delete_user(user_id):
    user = _get_member(user_id)
    if user.id == current_user.id:
        flash("No podés eliminar tu propia cuenta.", "error")
        return redirect(url_for("account.users"))
    name = user.name
    db.session.delete(user)
    log_audit("user", user_id, "eliminado", f"{name} eliminado de la empresa.",
              current_user, company_id=current_user.company_id)
    db.session.commit()
    flash(f"Usuario «{name}» eliminado.", "success")
    return redirect(url_for("account.users"))
