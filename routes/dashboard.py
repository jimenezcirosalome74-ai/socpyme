"""Panel interno: dashboard principal."""
from flask import Blueprint, render_template
from flask_login import login_required

from models import Event
from services import dashboard_stats

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/panel")
@login_required
def index():
    stats = dashboard_stats()
    recent_events = Event.query.order_by(Event.timestamp.desc()).limit(10).all()
    return render_template(
        "dashboard/index.html",
        stats=stats,
        recent_events=recent_events,
    )
