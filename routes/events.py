"""Eventos de seguridad: lista con filtros, detalle y cambio de estado."""
from datetime import datetime

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, abort, current_app,
)
from flask_login import login_required

from extensions import db
from models import Event, SEVERITIES, EVENT_STATES
from forms import EventStatusForm

events_bp = Blueprint("events", __name__, url_prefix="/eventos")


def _parse_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except (ValueError, TypeError):
        return None


@events_bp.route("/")
@login_required
def list_events():
    q = Event.query

    severity = request.args.get("severity", "").strip()
    status = request.args.get("status", "").strip()
    search = request.args.get("q", "").strip()
    date_from = request.args.get("from", "").strip()
    date_to = request.args.get("to", "").strip()

    if severity in SEVERITIES:
        q = q.filter(Event.severity == severity)
    if status in EVENT_STATES:
        q = q.filter(Event.status == status)
    if search:
        like = f"%{search}%"
        q = q.filter(
            db.or_(
                Event.event_type.ilike(like),
                Event.description.ilike(like),
                Event.source_ip.ilike(like),
            )
        )
    df = _parse_date(date_from)
    dt = _parse_date(date_to)
    if df:
        q = q.filter(Event.timestamp >= df)
    if dt:
        # incluir todo el día "to"
        q = q.filter(Event.timestamp < dt.replace(hour=23, minute=59, second=59))

    page = request.args.get("page", 1, type=int)
    per_page = current_app.config.get("EVENTS_PER_PAGE", 15)
    pagination = q.order_by(Event.timestamp.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return render_template(
        "events/list.html",
        pagination=pagination,
        events=pagination.items,
        filters={
            "severity": severity, "status": status, "q": search,
            "from": date_from, "to": date_to,
        },
        severities=SEVERITIES,
        statuses=EVENT_STATES,
    )


@events_bp.route("/<int:event_id>")
@login_required
def detail(event_id):
    event = db.session.get(Event, event_id)
    if event is None:
        abort(404)
    form = EventStatusForm(status=event.status)
    return render_template("events/detail.html", event=event, form=form)


@events_bp.route("/<int:event_id>/estado", methods=["POST"])
@login_required
def change_status(event_id):
    event = db.session.get(Event, event_id)
    if event is None:
        abort(404)
    form = EventStatusForm()
    if form.validate_on_submit():
        event.status = form.status.data
        db.session.commit()
        flash(f"Evento marcado como «{event.status_label}».", "success")
    else:
        flash("No se pudo cambiar el estado.", "error")
    return redirect(url_for("events.detail", event_id=event.id))
