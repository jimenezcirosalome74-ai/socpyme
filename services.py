"""Lógica de negocio compartida: evaluación de reglas de alerta."""
from datetime import timedelta

from extensions import db
from models import (
    Event, AlertRule, Notification, IncidentLog, Incident, AuditLog, utcnow,
)


def evaluate_alerts():
    """Revisa todas las reglas activas y genera notificaciones si se superan umbrales.

    Devuelve la lista de notificaciones creadas. Se llama después de insertar
    eventos (simulador o API) para que las alertas aparezcan en la campanita.
    """
    created = []
    now = utcnow()
    rules = AlertRule.query.filter_by(active=True).all()

    for rule in rules:
        window_start = now - timedelta(minutes=rule.window_minutes)
        count = (
            Event.query.filter(
                Event.severity == rule.target_severity,
                Event.timestamp >= window_start,
            ).count()
        )

        if count < rule.threshold:
            continue

        # Evitar spam: no disparar la misma regla dentro de su propia ventana
        if rule.last_triggered_at and rule.last_triggered_at >= window_start:
            continue

        rule.last_triggered_at = now
        notif = Notification(
            kind="alerta",
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


def log_audit(entity_type, entity_id, action, detail, user=None):
    """Registra un cambio en la bitácora de auditoría genérica."""
    entry = AuditLog(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        detail=detail,
        user_id=user.id if user else None,
    )
    db.session.add(entry)
    return entry


def dashboard_stats():
    """Calcula KPIs y series para el dashboard y el endpoint /api/dashboard."""
    now = utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    events_today = Event.query.filter(Event.timestamp >= today_start).count()
    critical_today = Event.query.filter(
        Event.timestamp >= today_start, Event.severity == "critico"
    ).count()
    resolved_today = Event.query.filter(
        Event.timestamp >= today_start, Event.status == "resuelto"
    ).count()
    resolution_rate = round((resolved_today / events_today) * 100, 1) if events_today else 0.0

    # Serie de 7 días (conteo por día)
    labels_7d, series_7d = [], []
    dias = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
    for offset in range(6, -1, -1):
        day_start = (today_start - timedelta(days=offset))
        day_end = day_start + timedelta(days=1)
        c = Event.query.filter(
            Event.timestamp >= day_start, Event.timestamp < day_end
        ).count()
        labels_7d.append(dias[day_start.weekday()])
        series_7d.append(c)

    # Distribución por severidad (todos los eventos)
    by_sev = {
        s: Event.query.filter_by(severity=s).count()
        for s in ("critico", "aviso", "info")
    }

    open_incidents = Incident.query.filter(Incident.status != "cerrado").count()

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
