"""API REST JSON de SOC-PYME.

Endpoints:
  GET  /api/dashboard              -> KPIs, series de gráficos y notificaciones
  GET  /api/events                 -> lista de eventos (con filtros)
  POST /api/events                 -> inyección de eventos por sistemas externos
  GET  /api/incidents              -> lista de incidentes
  POST /api/incidents              -> crear incidente
  PATCH /api/incidents/<id>        -> actualizar incidente
  POST /api/notifications/<id>/read
  POST /api/notifications/read-all
"""
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user

from extensions import db
from models import (
    Event, Incident, Notification, SEVERITIES, EVENT_STATES, INCIDENT_STATES, utcnow,
)
from services import evaluate_alerts, dashboard_stats, log_incident_change

api_bp = Blueprint("api", __name__, url_prefix="/api")


def error(message, code=400):
    return jsonify({"ok": False, "error": message}), code


# ---------------------------------------------------------------------------
# Dashboard (polling)
# ---------------------------------------------------------------------------
@api_bp.route("/dashboard")
@login_required
def dashboard():
    stats = dashboard_stats()
    recent = [e.to_dict() for e in Event.query.order_by(Event.timestamp.desc()).limit(10).all()]
    notifs = (
        Notification.query.filter_by(read=False)
        .order_by(Notification.created_at.desc())
        .limit(10)
        .all()
    )
    return jsonify({
        "ok": True,
        **stats,
        "recent_events": recent,
        "notifications": {
            "unread": Notification.query.filter_by(read=False).count(),
            "items": [n.to_dict() for n in notifs],
        },
    })


# ---------------------------------------------------------------------------
# Eventos
# ---------------------------------------------------------------------------
@api_bp.route("/events", methods=["GET"])
@login_required
def list_events():
    q = Event.query
    severity = request.args.get("severity")
    status = request.args.get("status")
    if severity in SEVERITIES:
        q = q.filter(Event.severity == severity)
    if status in EVENT_STATES:
        q = q.filter(Event.status == status)
    limit = min(request.args.get("limit", 50, type=int), 200)
    events = q.order_by(Event.timestamp.desc()).limit(limit).all()
    return jsonify({"ok": True, "count": len(events), "events": [e.to_dict() for e in events]})


@api_bp.route("/events", methods=["POST"])
def create_event():
    """Inyección de eventos por sistemas externos (sin sesión, CSRF exento).

    Ejemplo:
      curl -X POST http://localhost:5000/api/events \\
        -H "Content-Type: application/json" \\
        -d '{"severity":"critico","type":"Acceso SSH no autorizado",
             "description":"Puerto 22","source_ip":"203.0.113.9"}'
    """
    data = request.get_json(silent=True) or {}
    severity = (data.get("severity") or "info").lower()
    event_type = (data.get("type") or data.get("event_type") or "").strip()

    if severity not in SEVERITIES:
        return error(f"severity debe ser uno de {SEVERITIES}")
    if not event_type:
        return error("El campo 'type' es obligatorio")

    event = Event(
        severity=severity,
        event_type=event_type[:120],
        description=(data.get("description") or "")[:2000],
        source_ip=(data.get("source_ip") or "")[:45],
        status="nuevo",
    )
    db.session.add(event)
    db.session.commit()

    triggered = evaluate_alerts()
    return jsonify({
        "ok": True,
        "event": event.to_dict(),
        "alerts_triggered": len(triggered),
    }), 201


# ---------------------------------------------------------------------------
# Incidentes
# ---------------------------------------------------------------------------
@api_bp.route("/incidents", methods=["GET"])
@login_required
def list_incidents():
    q = Incident.query
    status = request.args.get("status")
    if status in INCIDENT_STATES:
        q = q.filter(Incident.status == status)
    incidents = q.order_by(Incident.created_at.desc()).all()
    return jsonify({"ok": True, "count": len(incidents), "incidents": [i.to_dict() for i in incidents]})


@api_bp.route("/incidents", methods=["POST"])
@login_required
def create_incident():
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    if not title:
        return error("El campo 'title' es obligatorio")
    severity = (data.get("severity") or "aviso").lower()
    if severity not in SEVERITIES:
        return error(f"severity debe ser uno de {SEVERITIES}")

    incident = Incident(
        title=title[:200],
        description=(data.get("description") or "")[:4000],
        severity=severity,
        status="abierto",
        event_id=data.get("event_id"),
    )
    db.session.add(incident)
    db.session.flush()
    log_incident_change(incident, "creado", f"Creado vía API por {current_user.name}.", current_user)
    db.session.commit()
    return jsonify({"ok": True, "incident": incident.to_dict()}), 201


@api_bp.route("/incidents/<int:incident_id>", methods=["PATCH"])
@login_required
def patch_incident(incident_id):
    incident = db.session.get(Incident, incident_id)
    if incident is None:
        return error("Incidente no encontrado", 404)

    data = request.get_json(silent=True) or {}
    if "status" in data:
        status = data["status"]
        if status not in INCIDENT_STATES:
            return error(f"status debe ser uno de {INCIDENT_STATES}")
        old = incident.status_label
        incident.status = status
        incident.closed_at = utcnow() if status == "cerrado" else None
        log_incident_change(incident, "estado", f"{old} → {incident.status_label} (API)", current_user)
    if "assignee_id" in data:
        incident.assignee_id = data["assignee_id"] or None
        log_incident_change(incident, "asignado", "Reasignado vía API.", current_user)
    if "severity" in data and data["severity"] in SEVERITIES:
        incident.severity = data["severity"]

    db.session.commit()
    return jsonify({"ok": True, "incident": incident.to_dict()})


# ---------------------------------------------------------------------------
# Notificaciones
# ---------------------------------------------------------------------------
@api_bp.route("/notifications/<int:notif_id>/read", methods=["POST"])
@login_required
def mark_read(notif_id):
    notif = db.session.get(Notification, notif_id)
    if notif is None:
        return error("Notificación no encontrada", 404)
    notif.read = True
    db.session.commit()
    return jsonify({"ok": True})


@api_bp.route("/notifications/read-all", methods=["POST"])
@login_required
def mark_all_read():
    Notification.query.filter_by(read=False).update({"read": True})
    db.session.commit()
    return jsonify({"ok": True})
