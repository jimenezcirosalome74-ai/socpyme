"""Reglas de alerta: listar, crear, editar, activar/desactivar y eliminar."""
from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, abort,
)
from flask_login import login_required, current_user

from extensions import db
from models import AlertRule, AuditLog
from forms import AlertRuleForm
from services import log_audit

alerts_bp = Blueprint("alerts", __name__, url_prefix="/alertas")


@alerts_bp.route("/")
@login_required
def list_rules():
    rules = AlertRule.query.order_by(AlertRule.id.asc()).all()
    logs = (
        AuditLog.query.filter_by(entity_type="alert_rule")
        .order_by(AuditLog.timestamp.desc())
        .limit(12)
        .all()
    )
    return render_template("alerts/list.html", rules=rules, logs=logs)


@alerts_bp.route("/nueva", methods=["GET", "POST"])
@login_required
def new():
    form = AlertRuleForm()
    if form.validate_on_submit():
        rule = AlertRule(
            name=form.name.data.strip(),
            target_severity=form.target_severity.data,
            threshold=form.threshold.data,
            window_minutes=form.window_minutes.data,
            channel=form.channel.data,
            active=form.active.data,
        )
        db.session.add(rule)
        db.session.flush()
        log_audit(
            "alert_rule", rule.id, "creada",
            f"Regla «{rule.name}»: {rule.threshold} eventos {rule.target_severity} "
            f"en {rule.window_minutes} min · canal {rule.channel_label}.",
            current_user,
        )
        db.session.commit()
        flash(f"Regla de alerta «{rule.name}» creada.", "success")
        return redirect(url_for("alerts.list_rules"))

    return render_template("alerts/form.html", form=form, mode="new", rule=None)


@alerts_bp.route("/<int:rule_id>/editar", methods=["GET", "POST"])
@login_required
def edit(rule_id):
    rule = db.session.get(AlertRule, rule_id)
    if rule is None:
        abort(404)

    form = AlertRuleForm(obj=rule)
    if form.validate_on_submit():
        rule.name = form.name.data.strip()
        rule.target_severity = form.target_severity.data
        rule.threshold = form.threshold.data
        rule.window_minutes = form.window_minutes.data
        rule.channel = form.channel.data
        rule.active = form.active.data
        log_audit(
            "alert_rule", rule.id, "editada",
            f"Regla «{rule.name}» actualizada: {rule.threshold} eventos "
            f"{rule.target_severity} en {rule.window_minutes} min · canal {rule.channel_label}.",
            current_user,
        )
        db.session.commit()
        flash(f"Regla «{rule.name}» actualizada.", "success")
        return redirect(url_for("alerts.list_rules"))

    return render_template("alerts/form.html", form=form, mode="edit", rule=rule)


@alerts_bp.route("/<int:rule_id>/toggle", methods=["POST"])
@login_required
def toggle(rule_id):
    rule = db.session.get(AlertRule, rule_id)
    if rule is None:
        abort(404)
    rule.active = not rule.active
    estado = "activada" if rule.active else "desactivada"
    log_audit("alert_rule", rule.id, estado, f"Regla «{rule.name}» {estado}.", current_user)
    db.session.commit()
    flash(f"Regla «{rule.name}» {estado}.", "success")
    return redirect(url_for("alerts.list_rules"))


@alerts_bp.route("/<int:rule_id>/eliminar", methods=["POST"])
@login_required
def delete(rule_id):
    rule = db.session.get(AlertRule, rule_id)
    if rule is None:
        abort(404)
    name = rule.name
    db.session.delete(rule)
    # La bitácora conserva el registro de la eliminación (entity_id apunta al id borrado)
    log_audit("alert_rule", rule_id, "eliminada", f"Regla «{name}» eliminada.", current_user)
    db.session.commit()
    flash(f"Regla «{name}» eliminada.", "success")
    return redirect(url_for("alerts.list_rules"))
