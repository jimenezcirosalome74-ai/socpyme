"""Modelos SQLAlchemy de SOC-PYME Solutions."""
from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db, login_manager


def utcnow():
    """Fecha/hora actual en UTC (naive para SQLite, comparaciones consistentes)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Constantes de dominio
# ---------------------------------------------------------------------------
SEVERITIES = ("critico", "aviso", "info")
EVENT_STATES = ("nuevo", "revisado", "resuelto")
INCIDENT_STATES = ("abierto", "en_progreso", "escalado", "cerrado")

SEVERITY_LABELS = {"critico": "CRÍTICO", "aviso": "AVISO", "info": "INFO"}
EVENT_STATE_LABELS = {"nuevo": "Nuevo", "revisado": "Revisado", "resuelto": "Resuelto"}
INCIDENT_STATE_LABELS = {
    "abierto": "Abierto",
    "en_progreso": "En progreso",
    "escalado": "Escalado",
    "cerrado": "Cerrado",
}

# Canales de notificación de las reglas de alerta
ALERT_CHANNELS = ("in_app", "email", "webhook", "sms")
ALERT_CHANNEL_LABELS = {
    "in_app": "En la app",
    "email": "Email",
    "webhook": "Webhook",
    "sms": "SMS",
}


# ---------------------------------------------------------------------------
# Usuario
# ---------------------------------------------------------------------------
class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    company = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    incidents = db.relationship("Incident", back_populates="assignee", lazy="dynamic")
    notifications = db.relationship(
        "Notification", back_populates="user", lazy="dynamic",
        cascade="all, delete-orphan",
    )

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)

    @property
    def initials(self):
        parts = self.name.split()
        if len(parts) >= 2:
            return (parts[0][0] + parts[1][0]).upper()
        return self.name[:2].upper()

    def __repr__(self):
        return f"<User {self.email}>"


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ---------------------------------------------------------------------------
# Eventos de seguridad
# ---------------------------------------------------------------------------
class Event(db.Model):
    __tablename__ = "events"

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)
    severity = db.Column(db.String(20), nullable=False, index=True)   # critico/aviso/info
    event_type = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    source_ip = db.Column(db.String(45), nullable=False, default="")
    status = db.Column(db.String(20), nullable=False, default="nuevo", index=True)

    incidents = db.relationship("Incident", back_populates="event", lazy="dynamic")

    @property
    def severity_label(self):
        return SEVERITY_LABELS.get(self.severity, self.severity.upper())

    @property
    def status_label(self):
        return EVENT_STATE_LABELS.get(self.status, self.status)

    def to_dict(self):
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "severity": self.severity,
            "severity_label": self.severity_label,
            "type": self.event_type,
            "description": self.description,
            "source_ip": self.source_ip,
            "status": self.status,
            "status_label": self.status_label,
        }

    def __repr__(self):
        return f"<Event {self.id} {self.severity} {self.event_type}>"


# ---------------------------------------------------------------------------
# Incidentes
# ---------------------------------------------------------------------------
class Incident(db.Model):
    __tablename__ = "incidents"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    severity = db.Column(db.String(20), nullable=False, default="aviso")
    status = db.Column(db.String(20), nullable=False, default="abierto", index=True)

    assignee_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=True)

    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    closed_at = db.Column(db.DateTime, nullable=True)

    assignee = db.relationship("User", back_populates="incidents")
    event = db.relationship("Event", back_populates="incidents")
    logs = db.relationship(
        "IncidentLog", back_populates="incident", lazy="dynamic",
        cascade="all, delete-orphan", order_by="IncidentLog.timestamp.desc()",
    )

    @property
    def severity_label(self):
        return SEVERITY_LABELS.get(self.severity, self.severity.upper())

    @property
    def status_label(self):
        return INCIDENT_STATE_LABELS.get(self.status, self.status)

    @property
    def is_open(self):
        return self.status != "cerrado"

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "severity": self.severity,
            "severity_label": self.severity_label,
            "status": self.status,
            "status_label": self.status_label,
            "assignee": self.assignee.name if self.assignee else None,
            "assignee_id": self.assignee_id,
            "event_id": self.event_id,
            "created_at": self.created_at.isoformat(),
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
        }

    def __repr__(self):
        return f"<Incident {self.id} {self.status} {self.title!r}>"


class IncidentLog(db.Model):
    """Bitácora de cambios de un incidente (trazabilidad completa)."""
    __tablename__ = "incident_logs"

    id = db.Column(db.Integer, primary_key=True)
    incident_id = db.Column(db.Integer, db.ForeignKey("incidents.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    action = db.Column(db.String(80), nullable=False)     # ej: "creado", "estado", "asignado"
    detail = db.Column(db.String(400), nullable=False, default="")
    timestamp = db.Column(db.DateTime, default=utcnow, nullable=False)

    incident = db.relationship("Incident", back_populates="logs")
    user = db.relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "action": self.action,
            "detail": self.detail,
            "user": self.user.name if self.user else "Sistema",
            "timestamp": self.timestamp.isoformat(),
        }


# ---------------------------------------------------------------------------
# Reglas de alerta
# ---------------------------------------------------------------------------
class AlertRule(db.Model):
    __tablename__ = "alert_rules"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    target_severity = db.Column(db.String(20), nullable=False, default="critico")
    threshold = db.Column(db.Integer, nullable=False, default=3)     # nº de eventos
    window_minutes = db.Column(db.Integer, nullable=False, default=5)
    channel = db.Column(db.String(20), nullable=False, default="in_app")
    active = db.Column(db.Boolean, default=True, nullable=False)
    last_triggered_at = db.Column(db.DateTime, nullable=True)

    @property
    def severity_label(self):
        return SEVERITY_LABELS.get(self.target_severity, self.target_severity.upper())

    @property
    def channel_label(self):
        return ALERT_CHANNEL_LABELS.get(self.channel, self.channel)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "target_severity": self.target_severity,
            "threshold": self.threshold,
            "window_minutes": self.window_minutes,
            "channel": self.channel,
            "active": self.active,
            "last_triggered_at": self.last_triggered_at.isoformat()
            if self.last_triggered_at else None,
        }

    def __repr__(self):
        return f"<AlertRule {self.name}>"


class AuditLog(db.Model):
    """Bitácora genérica de auditoría (ej: cambios en reglas de alerta)."""
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    entity_type = db.Column(db.String(40), nullable=False)   # ej: "alert_rule"
    entity_id = db.Column(db.Integer, nullable=True)
    action = db.Column(db.String(80), nullable=False)        # creada/editada/activada/eliminada
    detail = db.Column(db.String(400), nullable=False, default="")
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    timestamp = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)

    user = db.relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "action": self.action,
            "detail": self.detail,
            "user": self.user.name if self.user else "Sistema",
            "timestamp": self.timestamp.isoformat(),
        }


# ---------------------------------------------------------------------------
# Notificaciones internas (campanita del topbar)
# ---------------------------------------------------------------------------
class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)  # None = global
    kind = db.Column(db.String(20), nullable=False, default="alerta")
    message = db.Column(db.String(300), nullable=False)
    read = db.Column(db.Boolean, default=False, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)

    incident_id = db.Column(db.Integer, db.ForeignKey("incidents.id"), nullable=True)

    user = db.relationship("User", back_populates="notifications")

    def to_dict(self):
        return {
            "id": self.id,
            "kind": self.kind,
            "message": self.message,
            "read": self.read,
            "created_at": self.created_at.isoformat(),
            "incident_id": self.incident_id,
        }
