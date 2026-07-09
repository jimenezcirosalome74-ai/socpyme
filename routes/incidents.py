"""Gestión de incidentes: CRUD, cambio de estado, asignación y bitácora."""
from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, abort,
)
from flask_login import login_required, current_user

from extensions import db
from models import (
    Incident, Event, User, INCIDENT_STATES, SEVERITIES, utcnow,
)
from forms import IncidentForm, IncidentUpdateForm
from services import log_incident_change

incidents_bp = Blueprint("incidents", __name__, url_prefix="/incidentes")


def _assignee_choices():
    choices = [(0, "— Sin asignar —")]
    choices += [(u.id, f"{u.name} ({u.company})") for u in User.query.order_by(User.name).all()]
    return choices


@incidents_bp.route("/")
@login_required
def list_incidents():
    q = Incident.query
    status = request.args.get("status", "").strip()
    severity = request.args.get("severity", "").strip()

    if status in INCIDENT_STATES:
        q = q.filter(Incident.status == status)
    if severity in SEVERITIES:
        q = q.filter(Incident.severity == severity)

    incidents = q.order_by(Incident.created_at.desc()).all()
    return render_template(
        "incidents/list.html",
        incidents=incidents,
        filters={"status": status, "severity": severity},
        statuses=INCIDENT_STATES,
        severities=SEVERITIES,
    )


@incidents_bp.route("/nuevo", methods=["GET", "POST"])
@login_required
def new():
    form = IncidentForm()
    form.assignee_id.choices = _assignee_choices()

    # Prefill desde un evento (?event_id=)
    event = None
    event_id = request.values.get("event_id", type=int)
    if event_id:
        event = db.session.get(Event, event_id)

    if request.method == "GET" and event:
        form.title.data = f"Incidente: {event.event_type}"
        form.description.data = (
            f"Generado desde evento #{event.id} ({event.severity_label}).\n"
            f"IP origen: {event.source_ip}\n\n{event.description}"
        )
        form.severity.data = event.severity
        form.event_id.data = str(event.id)

    if form.validate_on_submit():
        assignee_id = form.assignee_id.data or None
        linked_event_id = form.event_id.data
        linked_event_id = int(linked_event_id) if linked_event_id and linked_event_id.isdigit() else None

        incident = Incident(
            title=form.title.data.strip(),
            description=(form.description.data or "").strip(),
            severity=form.severity.data,
            status="abierto",
            assignee_id=assignee_id if assignee_id else None,
            event_id=linked_event_id,
        )
        db.session.add(incident)
        db.session.flush()  # obtener id para la bitácora

        log_incident_change(incident, "creado", f"Incidente creado por {current_user.name}.", current_user)
        if linked_event_id:
            log_incident_change(incident, "vinculado", f"Vinculado al evento #{linked_event_id}.", current_user)
        db.session.commit()

        flash("Incidente creado correctamente.", "success")
        return redirect(url_for("incidents.detail", incident_id=incident.id))

    return render_template("incidents/new.html", form=form, event=event)


@incidents_bp.route("/<int:incident_id>")
@login_required
def detail(incident_id):
    incident = db.session.get(Incident, incident_id)
    if incident is None:
        abort(404)
    form = IncidentUpdateForm(status=incident.status, assignee_id=incident.assignee_id or 0)
    form.assignee_id.choices = _assignee_choices()
    logs = incident.logs.all()
    return render_template("incidents/detail.html", incident=incident, form=form, logs=logs)


@incidents_bp.route("/<int:incident_id>/actualizar", methods=["POST"])
@login_required
def update(incident_id):
    incident = db.session.get(Incident, incident_id)
    if incident is None:
        abort(404)

    form = IncidentUpdateForm()
    form.assignee_id.choices = _assignee_choices()

    if not form.validate_on_submit():
        flash("Datos inválidos, no se aplicaron los cambios.", "error")
        return redirect(url_for("incidents.detail", incident_id=incident.id))

    changes = []

    # Cambio de estado
    new_status = form.status.data
    if new_status != incident.status:
        old = incident.status_label
        incident.status = new_status
        if new_status == "cerrado":
            incident.closed_at = utcnow()
        else:
            incident.closed_at = None
        changes.append(f"estado: {old} → {incident.status_label}")
        log_incident_change(incident, "estado", f"{old} → {incident.status_label}", current_user)

    # Cambio de asignación
    new_assignee = form.assignee_id.data or None
    current_assignee = incident.assignee_id or None
    if new_assignee != current_assignee:
        incident.assignee_id = new_assignee if new_assignee else None
        who = db.session.get(User, new_assignee).name if new_assignee else "Sin asignar"
        changes.append(f"asignado a {who}")
        log_incident_change(incident, "asignado", f"Asignado a {who}.", current_user)

    # Nota opcional
    if form.note.data:
        log_incident_change(incident, "nota", form.note.data.strip(), current_user)
        changes.append("nota agregada")

    if changes:
        db.session.commit()
        flash("Incidente actualizado: " + "; ".join(changes) + ".", "success")
    else:
        flash("No hubo cambios que guardar.", "warning")

    return redirect(url_for("incidents.detail", incident_id=incident.id))
