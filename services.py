"""Lógica de negocio compartida: multi-tenancy, alertas y bitácora."""
from datetime import timedelta

from extensions import db
from models import (
    Event, AlertRule, Notification, IncidentLog, Incident, AuditLog, utcnow,
)


# ---------------------------------------------------------------------------
# Multi-tenancy: aislamiento de datos por empresa
# ---------------------------------------------------------------------------
def visible_company_id(user):
    """Devuelve la empresa a la que el usuario está limitado.

    None => ve TODAS las empresas (rol analista del SOC).
    """
    return None if user.is_global else user.company_id


def can_access(user, obj):
    """¿El usuario puede ver/editar un objeto con `company_id`?"""
    if user.is_global:
        return True
    return getattr(obj, "company_id", None) == user.company_id


def scope_by_company(query, model, user):
    """Filtra una consulta por la empresa del usuario (salvo analista)."""
    cid = visible_company_id(user)
    if cid is not None:
        query = query.filter(model.company_id == cid)
    return query


def notifications_query(user):
    """Notificaciones visibles para el usuario (su empresa + globales)."""
    q = Notification.query
    if not user.is_global:
        q = q.filter(
            db.or_(
                Notification.company_id == user.company_id,
                Notification.company_id.is_(None),  # avisos globales del sistema
            )
        )
    return q


def evaluate_alerts():
    """Revisa las reglas activas de cada empresa y genera notificaciones.

    Cuenta solo los eventos de la MISMA empresa que la regla, y crea la
    notificación con ese company_id para que llegue al tenant correcto.
    Se llama tras insertar eventos (simulador o API).
    """
    created = []
    now = utcnow()
    rules = AlertRule.query.filter_by(active=True).all()

    for rule in rules:
        window_start = now - timedelta(minutes=rule.window_minutes)
        q = Event.query.filter(
            Event.severity == rule.target_severity,
            Event.timestamp >= window_start,
        )
        if rule.company_id is not None:
            q = q.filter(Event.company_id == rule.company_id)
        count = q.count()

        if count < rule.threshold:
            continue

        # Evitar spam: no disparar la misma regla dentro de su propia ventana
        if rule.last_triggered_at and rule.last_triggered_at >= window_start:
            continue

        rule.last_triggered_at = now
        notif = Notification(
            kind="alerta",
            company_id=rule.company_id,
            message=(
                f"⚠ Regla «{rule.name}»: {count} eventos "
                f"{rule.target_severity} en los últimos {rule.window_minutes} min "
                f"(umbral {rule.threshold}) · canal: {rule.channel_label}."
            ),
        )
        db.session.add(notif)
        created.append(notif)

    if created:
        db.session.commit()
    return created


def log_incident_change(incident, action, detail, user=None):
    """Registra un cambio en la bitácora del incidente."""
    entry = IncidentLog(
        incident_id=incident.id,
        user_id=user.id if user else None,
        action=action,
        detail=detail,
    )
    db.session.add(entry)
    return entry


def log_audit(entity_type, entity_id, action, detail, user=None, company_id=None):
    """Registra un cambio en la bitácora de auditoría genérica."""
    entry = AuditLog(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        detail=detail,
        user_id=user.id if user else None,
        company_id=company_id,
    )
    db.session.add(entry)
    return entry


def dashboard_stats(user):
    """KPIs y series para el dashboard, acotados a la empresa del usuario."""
    now = utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    cid = visible_company_id(user)

    def evq():
        q = Event.query
        return q if cid is None else q.filter(Event.company_id == cid)

    events_today = evq().filter(Event.timestamp >= today_start).count()
    critical_today = evq().filter(
        Event.timestamp >= today_start, Event.severity == "critico"
    ).count()
    resolved_today = evq().filter(
        Event.timestamp >= today_start, Event.status == "resuelto"
    ).count()
    resolution_rate = round((resolved_today / events_today) * 100, 1) if events_today else 0.0

    # Serie de 7 días (conteo por día)
    labels_7d, series_7d = [], []
    dias = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
    for offset in range(6, -1, -1):
        day_start = (today_start - timedelta(days=offset))
        day_end = day_start + timedelta(days=1)
        c = evq().filter(
            Event.timestamp >= day_start, Event.timestamp < day_end
        ).count()
        labels_7d.append(dias[day_start.weekday()])
        series_7d.append(c)

    # Distribución por severidad (eventos de la empresa)
    by_sev = {
        s: evq().filter(Event.severity == s).count()
        for s in ("critico", "aviso", "info")
    }

    inc_q = Incident.query.filter(Incident.status != "cerrado")
    if cid is not None:
        inc_q = inc_q.filter(Incident.company_id == cid)
    open_incidents = inc_q.count()

    return {
        "kpis": {
            "events_today": events_today,
            "critical_today": critical_today,
            "resolved_today": resolved_today,
            "resolution_rate": resolution_rate,
            "open_incidents": open_incidents,
        },
        "chart_7d": {"labels": labels_7d, "data": series_7d},
        "by_severity": by_sev,
        "generated_at": now.isoformat(),
    }
