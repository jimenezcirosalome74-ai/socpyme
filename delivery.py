"""Entrega real de alertas por sus canales: in-app, email (SMTP), webhook, SMS.

Cada intento se registra en `AlertDelivery` para trazabilidad. El diseño es
tolerante a fallos: un canal que falla no rompe la generación de eventos.
"""
import json
import smtplib
import urllib.request
from email.mime.text import MIMEText

from flask import current_app

from extensions import db
from models import AlertDelivery


def _record(rule, channel, destination, status, detail):
    entry = AlertDelivery(
        rule_id=rule.id,
        company_id=rule.company_id,
        channel=channel,
        destination=(destination or "")[:300],
        status=status,
        detail=(detail or "")[:400],
    )
    db.session.add(entry)
    return entry


def deliver_alert(rule, message, count=None):
    """Entrega una alerta por el canal configurado en la regla y registra el intento."""
    channel = rule.channel
    dest = (rule.destination or "").strip()
    try:
        if channel == "in_app":
            _record(rule, channel, "", "enviada", "Notificación en la campanita.")
        elif channel == "email":
            _deliver_email(rule, dest, message)
        elif channel == "webhook":
            _deliver_webhook(rule, dest, message, count)
        elif channel == "sms":
            _record(rule, channel, dest, "omitida",
                    "SMS requiere un proveedor (ej. Twilio) que no está configurado.")
        else:
            _record(rule, channel, dest, "omitida", "Canal desconocido.")
    except Exception as exc:  # nunca dejar que una entrega tumbe el flujo
        _record(rule, channel, dest, "fallida", f"{type(exc).__name__}: {exc}")
    db.session.commit()


def _email_recipients(rule, dest):
    if dest:
        return [dest]
    # Sin destino explícito: avisar a los administradores de la empresa
    if rule.company is not None:
        return [u.email for u in rule.company.users if u.role in ("admin", "analista")]
    return []


def _deliver_email(rule, dest, message):
    recipients = [r for r in _email_recipients(rule, dest) if r]
    if not recipients:
        _record(rule, "email", dest, "omitida", "No hay destinatarios para el correo.")
        return

    host = current_app.config.get("SMTP_HOST")
    to_line = ", ".join(recipients)

    if not host:
        # Modo demo: sin SMTP configurado, se registra el correo simulado.
        _record(rule, "email", to_line, "enviada (dev)",
                "SMTP no configurado (SMTP_HOST). Correo simulado — configurá SMTP para envío real.")
        return

    msg = MIMEText(message, _charset="utf-8")
    msg["Subject"] = "🔔 Alerta de seguridad · SOC-PYME"
    msg["From"] = current_app.config.get("MAIL_FROM", "alertas@socpyme.co")
    msg["To"] = to_line

    port = int(current_app.config.get("SMTP_PORT", 587))
    with smtplib.SMTP(host, port, timeout=8) as server:
        if current_app.config.get("SMTP_USE_TLS", True):
            server.starttls()
        user = current_app.config.get("SMTP_USER")
        pw = current_app.config.get("SMTP_PASSWORD")
        if user:
            server.login(user, pw)
        server.send_message(msg)
    _record(rule, "email", to_line, "enviada", "Correo enviado por SMTP.")


def _deliver_webhook(rule, dest, message, count):
    if not dest:
        _record(rule, "webhook", "", "omitida", "La regla no tiene URL de webhook.")
        return

    payload = json.dumps({
        "rule": rule.name,
        "company_id": rule.company_id,
        "severity": rule.target_severity,
        "count": count,
        "message": message,
    }).encode("utf-8")

    req = urllib.request.Request(
        dest, data=payload, method="POST",
        headers={"Content-Type": "application/json", "User-Agent": "SOC-PYME-Alertas/1.0"},
    )
    timeout = int(current_app.config.get("ALERT_WEBHOOK_TIMEOUT", 4))
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (URL la define el usuario)
        code = resp.getcode()
    _record(rule, "webhook", dest, "enviada", f"POST respondió {code}.")
