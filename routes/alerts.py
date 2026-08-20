"""Reglas de alerta: listar, crear, editar, activar/desactivar y eliminar."""
from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, abort,
)
from flask_login import login_required, current_user

from extensions import db
from models import AlertRule, AuditLog, AlertDelivery
from forms import AlertRuleForm
from services import log_audit, scope_by_company, can_access

alerts_bp = Blueprint("alerts", __name__, url_prefix="/alertas")


@alerts_bp.route("/")
@login_required
def list_rules():
    rules = (
        scope_by_company(AlertRule.query, AlertRule, current_user)
        .order_by(AlertRule.id.asc())
        .all()
    )
    log_q = AuditLog.query.filter_by(entity_type="alert_rule")
    del_q = AlertDelivery.query
    if not current_user.is_global:
        log_q = log_q.filter(AuditLog.company_id == current_user.company_id)
        del_q = del_q.filter(AlertDelivery.company_id == current_user.company_id)
    logs = log_q.order_by(AuditLog.timestamp.desc()).limit(12).all()
    deliveries = del_q.order_by(AlertDelivery.created_at.desc()).limit(10).all()
    return render_template("alerts/list.html", rules=rules, logs=logs, deliveries=deliveries)


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
            destination=(form.destination.data or "").strip(),
            active=form.active.data,
            company_id=current_user.company_id,
        )
        db.session.add(rule)
        db.session.flush()
        log_audit(
            "alert_rule", rule.id, "creada",
            f"Regla «{rule.name}»: {rule.threshold} eventos {rule.target_severity} "
            f"en {rule.window_minutes} min · canal {rule.channel_label}.",
            current_user, company_id=rule.company_id,
        )
        db.session.commit()
        flash(f"Regla de alerta «{rule.name}» creada.", "success")
        return redirect(url_for("alerts.list_rules"))

    return render_template("alerts/form.html", form=form, mode="new", rule=None)


@alerts_bp.route("/<int:rule_id>/editar", methods=["GET", "POST"])
@login_required
def edit(rule_id):
    rule = db.session.get(AlertRule, rule_id)
    if rule is None or not can_access(current_user, rule):
        abort(404)

    form = AlertRuleForm(obj=rule)
    if form.validate_on_submit():
        rule.name = form.name.data.strip()
        rule.target_severity = form.target_severity.data
        rule.threshold = form.threshold.data
        rule.window_minutes = form.window_minutes.data
        rule.channel = form.channel.data
        rule.destination = (form.destination.data or "").strip()
        rule.active = form.active.data
        log_audit(
            "alert_rule", rule.id, "editada",
            f"Regla «{rule.name}» actualizada: {rule.threshold} eventos "
            f"{rule.target_severity} en {rule.window_minutes} min · canal {rule.channel_label}.",
            current_user, company_id=rule.company_id,
        )
        db.session.commit()
        flash(f"Regla «{rule.name}» actualizada.", "success")
        return redirect(url_for("alerts.list_rules"))

    return render_template("alerts/form.html", form=form, mode="edit", rule=rule)


@alerts_bp.route("/<int:rule_id>/toggle", methods=["POST"])
@login_required
def toggle(rule_id):
    rule = db.session.get(AlertRule, rule_id)
    if rule is None or not can_access(current_user, rule):
        abort(404)
    rule.active = not rule.active
    estado = "activada" if rule.active else "desactivada"
    log_audit("alert_rule", rule.id, estado, f"Regla «{rule.name}» {estado}.",
              current_user, company_id=rule.company_id)
    db.session.commit()
    flash(f"Regla «{rule.name}» {estado}.", "success")
    return redirect(url_for("alerts.list_rules"))


@alerts_bp.route("/<int:rule_id>/eliminar", methods=["POST"])
@login_required
def delete(rule_id):
    rule = db.session.get(AlertRule, rule_id)
    if rule is None or not can_access(current_user, rule):
        abort(404)
    name = rule.name
    cid = rule.company_id
    db.session.delete(rule)
    # La bitácora conserva el registro de la eliminación (entity_id apunta al id borrado)
    log_audit("alert_rule", rule_id, "eliminada", f"Regla «{name}» eliminada.",
              current_user, company_id=cid)
    db.session.commit()
    flash(f"Regla «{name}» eliminada.", "success")
    return redirect(url_for("alerts.list_rules"))
