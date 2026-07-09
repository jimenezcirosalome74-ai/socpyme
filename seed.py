"""Puebla la base de datos con datos demo realistas.

Uso:
    python seed.py          # recrea y puebla la BD
    flask seed              # equivalente vía CLI
"""
import random
import sys
from datetime import timedelta

# Consola UTF-8 en Windows (evita UnicodeEncodeError con emojis/acentos)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

from extensions import db
from models import (
    User, Event, Incident, IncidentLog, AlertRule, Notification, utcnow,
)
from simulator import make_event


def seed_database(app, reset=True):
    with app.app_context():
        if reset:
            db.drop_all()
            db.create_all()

        # --- Usuarios -------------------------------------------------------
        demo = User(name="Camila Restrepo", company="Ferretería El Tornillo SAS",
                    email="demo@socpyme.co")
        demo.set_password("Demo1234!")

        analyst = User(name="Julián Ospina", company="SOC-PYME Solutions",
                       email="julian@socpyme.co")
        analyst.set_password("Analista2026!")

        db.session.add_all([demo, analyst])
        db.session.commit()

        # --- Reglas de alerta ----------------------------------------------
        rules = [
            AlertRule(name="Pico de eventos críticos", target_severity="critico",
                      threshold=3, window_minutes=5, channel="email", active=True),
            AlertRule(name="Avalancha de avisos", target_severity="aviso",
                      threshold=8, window_minutes=10, channel="in_app", active=True),
        ]
        db.session.add_all(rules)
        db.session.commit()

        # --- Eventos históricos (últimos 7 días) ---------------------------
        now = utcnow()
        events = []
        for day in range(6, -1, -1):
            # más eventos hoy, menos hace días
            n = random.randint(18, 45) if day == 0 else random.randint(10, 30)
            day_base = now - timedelta(days=day)
            for _ in range(n):
                ev = make_event()
                ev.timestamp = day_base - timedelta(
                    hours=random.randint(0, 23), minutes=random.randint(0, 59)
                )
                # marcar la mayoría de eventos antiguos como resueltos
                if day > 0:
                    ev.status = random.choices(
                        ["resuelto", "revisado", "nuevo"], weights=[7, 2, 1]
                    )[0]
                else:
                    ev.status = random.choices(
                        ["resuelto", "revisado", "nuevo"], weights=[5, 2, 3]
                    )[0]
                events.append(ev)
        db.session.add_all(events)
        db.session.commit()

        # --- Incidentes demo -----------------------------------------------
        critical_events = [e for e in events if e.severity == "critico"][:4]
        incident_specs = [
            ("Acceso SSH sospechoso desde IP externa", "escalado", "critico"),
            ("Múltiples intentos de login a panel admin", "en_progreso", "aviso"),
            ("Revisión de certificado TLS próximo a expirar", "abierto", "aviso"),
            ("Malware bloqueado — análisis forense", "cerrado", "critico"),
        ]
        for idx, (title, status, sev) in enumerate(incident_specs):
            linked = critical_events[idx] if idx < len(critical_events) else None
            inc = Incident(
                title=title,
                description=f"Incidente de demostración generado por el seed. Severidad {sev}.",
                severity=sev,
                status=status,
                assignee_id=analyst.id if status != "abierto" else None,
                event_id=linked.id if linked else None,
                created_at=now - timedelta(hours=random.randint(2, 60)),
            )
            if status == "cerrado":
                inc.closed_at = now - timedelta(hours=random.randint(1, 5))
            db.session.add(inc)
            db.session.flush()

            db.session.add(IncidentLog(
                incident_id=inc.id, user_id=demo.id, action="creado",
                detail="Incidente creado desde el evento vinculado.",
                timestamp=inc.created_at,
            ))
            if status != "abierto":
                db.session.add(IncidentLog(
                    incident_id=inc.id, user_id=analyst.id, action="asignado",
                    detail=f"Asignado a {analyst.name}.",
                    timestamp=inc.created_at + timedelta(minutes=15),
                ))
            if status == "cerrado":
                db.session.add(IncidentLog(
                    incident_id=inc.id, user_id=analyst.id, action="estado",
                    detail="En progreso → Cerrado. Amenaza contenida.",
                    timestamp=inc.closed_at,
                ))
        db.session.commit()

        # --- Notificación de bienvenida ------------------------------------
        db.session.add(Notification(
            kind="info",
            message="Bienvenido a SOC-PYME. Ejecutá `flask simulate` para ver eventos en vivo.",
        ))
        db.session.commit()

        # --- Resumen --------------------------------------------------------
        print("✅ Base de datos poblada:")
        print(f"   Usuarios     : {User.query.count()}")
        print(f"   Eventos      : {Event.query.count()}")
        print(f"   Incidentes   : {Incident.query.count()}")
        print(f"   Reglas alerta: {AlertRule.query.count()}")
        print()
        print("   👤 Usuario demo: demo@socpyme.co  /  Demo1234!")


if __name__ == "__main__":
    from app import create_app
    seed_database(create_app())
