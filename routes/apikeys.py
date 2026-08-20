"""Claves API por empresa: listar, crear, activar/desactivar y eliminar.

Las claves autentican la inyección externa de eventos (POST /api/events) y
asocian cada evento a la empresa dueña de la clave (multi-tenancy).
"""
from flask import (
    Blueprint, render_template, redirect, url_for, flash, abort, session,
)
from flask_login import login_required, current_user

from extensions import db
from models import ApiKey
from forms import ApiKeyForm

apikeys_bp = Blueprint("apikeys", __name__, url_prefix="/claves-api")


@apikeys_bp.route("/", methods=["GET", "POST"])
@login_required
def index():
    form = ApiKeyForm()

    if form.validate_on_submit():
        if current_user.company_id is None:
            flash("Tu usuario no está asociado a una empresa.", "error")
            return redirect(url_for("apikeys.index"))
        key = ApiKey(
            company_id=current_user.company_id,
            name=form.name.data.strip(),
            token=ApiKey.generate_token(),
            active=True,
        )
        db.session.add(key)
        db.session.commit()
        # Mostrar el token completo una sola vez, tras el redirect
        session["reveal_key_id"] = key.id
        flash("Clave API creada. Copiala ahora: por seguridad se muestra una sola vez.", "success")
        return redirect(url_for("apikeys.index"))

    # Claves visibles: las de la empresa del usuario (analista: todas)
    q = ApiKey.query
    if not current_user.is_global:
        q = q.filter(ApiKey.company_id == current_user.company_id)
    keys = q.order_by(ApiKey.id.desc()).all()

    reveal_id = session.pop("reveal_key_id", None)
    return render_template("apikeys/index.html", form=form, keys=keys, reveal_id=reveal_id)


def _get_owned(key_id):
    key = db.session.get(ApiKey, key_id)
    if key is None:
        abort(404)
    if not current_user.is_global and key.company_id != current_user.company_id:
        abort(404)
    return key


@apikeys_bp.route("/<int:key_id>/toggle", methods=["POST"])
@login_required
def toggle(key_id):
    key = _get_owned(key_id)
    key.active = not key.active
    db.session.commit()
    flash(f"Clave «{key.name}» {'activada' if key.active else 'desactivada'}.", "success")
    return redirect(url_for("apikeys.index"))


@apikeys_bp.route("/<int:key_id>/eliminar", methods=["POST"])
@login_required
def delete(key_id):
    key = _get_owned(key_id)
    name = key.name
    db.session.delete(key)
    db.session.commit()
    flash(f"Clave «{name}» eliminada.", "success")
    return redirect(url_for("apikeys.index"))
