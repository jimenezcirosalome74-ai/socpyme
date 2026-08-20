"""Generación de reportes PDF de seguridad por empresa (RF: reportes)."""
from datetime import timedelta

from fpdf import FPDF
from sqlalchemy import func

from extensions import db
from models import Event, Incident, AlertRule, SEVERITIES, SEVERITY_LABELS, utcnow
from services import visible_company_id

# Paleta (coherente con la identidad de la app)
NAVY = (10, 37, 64)
CYAN = (46, 196, 182)
GRAY = (71, 85, 105)
LIGHT = (237, 242, 247)
RED = (239, 68, 68)
GREEN = (16, 185, 129)
YELLOW = (245, 158, 11)

SEV_COLOR = {"critico": RED, "aviso": YELLOW, "info": GREEN}


def _clean(text):
    """fpdf con fuentes core usa latin-1: reemplaza caracteres fuera de rango."""
    if text is None:
        return ""
    repl = {"—": "-", "→": "->", "≥": ">=", "•": "-", "…": "...", "⚠": "!"}
    out = str(text)
    for k, v in repl.items():
        out = out.replace(k, v)
    return out.encode("latin-1", "replace").decode("latin-1")


def report_data(user, days=30):
    """Reúne los datos del reporte, acotados a la empresa del usuario."""
    now = utcnow()
    start = now - timedelta(days=days)
    cid = visible_company_id(user)

    def evq():
        q = Event.query.filter(Event.timestamp >= start)
        return q if cid is None else q.filter(Event.company_id == cid)

    total = evq().count()
    by_sev = {s: evq().filter(Event.severity == s).count() for s in SEVERITIES}
    resolved = evq().filter(Event.status == "resuelto").count()
    rate = round(resolved / total * 100, 1) if total else 0.0

    top_types = (
        evq().with_entities(Event.event_type, func.count(Event.id).label("n"))
        .group_by(Event.event_type).order_by(func.count(Event.id).desc()).limit(8).all()
    )

    inc_q = Incident.query.filter(Incident.created_at >= start)
    if cid is not None:
        inc_q = inc_q.filter(Incident.company_id == cid)
    incidents = inc_q.order_by(Incident.created_at.desc()).limit(12).all()
    open_incidents = sum(1 for i in incidents if i.status != "cerrado")

    rule_q = AlertRule.query.filter_by(active=True)
    if cid is not None:
        rule_q = rule_q.filter(AlertRule.company_id == cid)
    rules = rule_q.all()

    company_name = "Todas las empresas" if cid is None else user.company_name

    return {
        "company": company_name,
        "days": days,
        "generated": now,
        "start": start,
        "kpis": {
            "total": total, "critical": by_sev["critico"],
            "resolved": resolved, "rate": rate, "open_incidents": open_incidents,
        },
        "by_severity": by_sev,
        "top_types": top_types,
        "incidents": incidents,
        "rules": rules,
    }


class _Report(FPDF):
    def header(self):
        self.set_fill_color(*NAVY)
        self.rect(0, 0, 210, 26, "F")
        self.set_xy(12, 7)
        self.set_font("Helvetica", "B", 16)
        self.set_text_color(255, 255, 255)
        self.cell(0, 6, "SOC-PYME Solutions", new_x="LMARGIN", new_y="NEXT")
        self.set_x(12)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*CYAN)
        self.cell(0, 5, "Reporte de seguridad", new_x="LMARGIN", new_y="NEXT")
        self.set_y(32)

    def footer(self):
        self.set_y(-14)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 5, "SOC-PYME Solutions - Confidencial", align="L")
        self.cell(0, 5, f"Pagina {self.page_no()}", align="R")


def _section(pdf, title):
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*NAVY)
    pdf.cell(0, 8, _clean(title), new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(*CYAN)
    pdf.set_line_width(0.6)
    y = pdf.get_y()
    pdf.line(12, y, 60, y)
    pdf.ln(3)


def _kpi_box(pdf, x, y, w, label, value, color=NAVY):
    pdf.set_xy(x, y)
    pdf.set_fill_color(*LIGHT)
    pdf.rect(x, y, w, 20, "F")
    pdf.set_xy(x + 3, y + 3)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*GRAY)
    pdf.cell(w - 6, 4, _clean(label.upper()), new_x="LMARGIN", new_y="NEXT")
    pdf.set_xy(x + 3, y + 9)
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(*color)
    pdf.cell(w - 6, 8, _clean(str(value)))


def build_report_pdf(user, days=30):
    """Devuelve los bytes de un PDF con el reporte de la empresa del usuario."""
    d = report_data(user, days)
    pdf = _Report()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    pdf.set_left_margin(12)
    pdf.set_right_margin(12)

    # Cabecera del reporte
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(*NAVY)
    pdf.cell(0, 8, _clean(d["company"]), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*GRAY)
    periodo = f"Periodo: ultimos {d['days']} dias ({d['start'].strftime('%d/%m/%Y')} - {d['generated'].strftime('%d/%m/%Y')})"
    pdf.cell(0, 6, _clean(periodo), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, _clean(f"Generado: {d['generated'].strftime('%d/%m/%Y %H:%M')} UTC"), new_x="LMARGIN", new_y="NEXT")

    # KPIs
    _section(pdf, "Resumen del periodo")
    y = pdf.get_y()
    k = d["kpis"]
    _kpi_box(pdf, 12, y, 44, "Eventos", k["total"])
    _kpi_box(pdf, 60, y, 44, "Criticos", k["critical"], RED)
    _kpi_box(pdf, 108, y, 44, "Resueltos", k["resolved"], GREEN)
    _kpi_box(pdf, 156, y, 42, "% Resolucion", f"{k['rate']}%")
    pdf.set_y(y + 24)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*GRAY)
    pdf.cell(0, 6, _clean(f"Incidentes abiertos en el periodo: {k['open_incidents']}"),
             new_x="LMARGIN", new_y="NEXT")

    # Distribución por severidad
    _section(pdf, "Distribucion por severidad")
    total = max(k["total"], 1)
    for sev in SEVERITIES:
        n = d["by_severity"][sev]
        pct = round(n / total * 100)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*SEV_COLOR[sev])
        pdf.cell(28, 6, _clean(SEVERITY_LABELS[sev]))
        # barra
        pdf.set_fill_color(*LIGHT)
        pdf.rect(42, pdf.get_y() + 1, 120, 4, "F")
        pdf.set_fill_color(*SEV_COLOR[sev])
        pdf.rect(42, pdf.get_y() + 1, max(1, 120 * n / total), 4, "F")
        pdf.set_text_color(*GRAY)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_xy(166, pdf.get_y())
        pdf.cell(0, 6, _clean(f"{n} ({pct}%)"), new_x="LMARGIN", new_y="NEXT")

    # Eventos por tipo
    _section(pdf, "Eventos mas frecuentes")
    if d["top_types"]:
        _table(pdf, ["Tipo de evento", "Cantidad"], [[t[0], str(t[1])] for t in d["top_types"]], [150, 36])
    else:
        _empty(pdf, "Sin eventos en el periodo.")

    # Incidentes
    _section(pdf, "Incidentes del periodo")
    if d["incidents"]:
        rows = [[f"#{i.id}", i.title[:42], i.severity_label, i.status_label,
                 i.created_at.strftime("%d/%m")] for i in d["incidents"]]
        _table(pdf, ["ID", "Titulo", "Severidad", "Estado", "Creado"], rows, [14, 92, 30, 30, 20])
    else:
        _empty(pdf, "Sin incidentes en el periodo.")

    # Reglas activas
    _section(pdf, "Reglas de alerta activas")
    if d["rules"]:
        rows = [[r.name[:44], r.severity_label, f">= {r.threshold}/{r.window_minutes}min",
                 r.channel_label] for r in d["rules"]]
        _table(pdf, ["Regla", "Severidad", "Condicion", "Canal"], rows, [72, 30, 46, 38])
    else:
        _empty(pdf, "Sin reglas activas.")

    return bytes(pdf.output())


def _table(pdf, headers, rows, widths):
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(*NAVY)
    pdf.set_text_color(255, 255, 255)
    for h, w in zip(headers, widths):
        pdf.cell(w, 7, _clean(h), border=0, fill=True, align="L")
    pdf.ln(7)
    pdf.set_font("Helvetica", "", 9)
    fill = False
    for row in rows:
        pdf.set_fill_color(*(LIGHT if fill else (255, 255, 255)))
        pdf.set_text_color(*GRAY)
        for val, w in zip(row, widths):
            pdf.cell(w, 6, _clean(val), border=0, fill=True, align="L")
        pdf.ln(6)
        fill = not fill


def _empty(pdf, text):
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 6, _clean(text), new_x="LMARGIN", new_y="NEXT")
