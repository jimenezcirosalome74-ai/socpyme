"""Reportes PDF de seguridad por empresa."""
from flask import Blueprint, render_template, request, Response
from flask_login import login_required, current_user

from reports import build_report_pdf, report_data

reports_bp = Blueprint("reports", __name__, url_prefix="/reportes")

VALID_PERIODS = (7, 30, 90)


def _days():
    days = request.args.get("days", 30, type=int)
    return days if days in VALID_PERIODS else 30


@reports_bp.route("/")
@login_required
def index():
    days = _days()
    data = report_data(current_user, days)
    return render_template("reports/index.html", data=data, days=days, periods=VALID_PERIODS)


@reports_bp.route("/pdf")
@login_required
def download():
    days = _days()
    pdf_bytes = build_report_pdf(current_user, days)
    company = (current_user.company_name or "socpyme").replace(" ", "_")
    filename = f"reporte_soc_{company}_{days}d.pdf"
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
