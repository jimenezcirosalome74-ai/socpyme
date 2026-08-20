"""Puebla la base de datos con datos demo realistas y multi-empresa.

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
    Company, User, Event, Incident, IncidentLog, AlertRule, ApiKey,
    Notification, utcnow,
)
from simulator import make_event


def seed_database(app, reset=True):
    with app.app_context():
        if reset:
            db.drop_all()
            db.create_all()

        # --- Empresas -------------------------------------------------------
        provider = Company(name="SOC-PYME Solutions", kind="proveedor")
        ferreteria = Company(name="Ferretería El Tornillo SAS", kind="cliente")
        panaderia = Company(name="Panadería La Espiga SAS", kind="cliente")
        db.session.add_all([provider, ferreteria, panaderia])
        db.session.commit()

        clientes = [ferreteria, panaderia]

        # --- Usuarios -------------------------------------------------------
        # Analista del SOC: ve TODAS las empresas
        analyst = User(name="Julián Ospina", email="julian@socpyme.co",
                       role="analista", company_id=provider.id)
        analyst.set_password("Analista2026!")

        # Admin de Ferretería (usuario demo)
        demo = User(name="Camila Restrepo", email="demo@socpyme.co",
                    role="admin", company_id=ferreteria.id)
        demo.set_password("Demo1234!")

        # Admin de Panadería (para probar el aislamiento entre empresas)
        panadero = User(name="Sofía Marín", email="sofia@laespiga.co",
                        role="admin", company_id=panaderia.id)
        panadero.set_password("Espiga2026!")

        db.session.add_all([analyst, demo, panadero])
        db.session.commit()

        # --- Reglas de alerta (una por empresa) ----------------------------
        db.session.add_all([
            AlertRule(name="Pico de eventos críticos", target_severity="critico",
                      threshold=3, window_minutes=5, channel="email",
                      active=True, company_id=ferreteria.id),
            AlertRule(name="Avalancha de avisos", target_severity="aviso",
                      threshold=8, window_minutes=10, channel="in_app",
                      active=True, company_id=ferreteria.id),
            AlertRule(name="Críticos en horario nocturno", target_severity="critico",
                      threshold=2, window_minutes=15, channel="sms",
                      active=True, company_id=panaderia.id),
        ])
        db.session.commit()

        # --- Claves API (una por empresa cliente) --------------------------
        for c in clientes:
            db.session.add(ApiKey(
                company_id=c.id,
                name=f"Servidor principal · {c.name.split()[0]}",
                token=ApiKey.generate_token(),
                active=True,
            ))
        db.session.commit()

        # --- Eventos históricos (últimos 7 días), repartidos por empresa ---
        now = utcnow()
        events = []
        for day in range(6, -1, -1):
            n = random.randint(18, 45) if day == 0 else random.randint(10, 30)
            day_base = now - timedelta(days=day)
            for _ in range(n):
                ev = make_event()
                ev.company_id = random.choice(clientes).id
                ev.timestamp = day_base - timedelta(
                    hours=random.randint(0, 23), minutes=random.randint(0, 59)
                )
                if day > 0:
                    ev.status = random.choices(
                        ["resuelto", "revisado", "nuevo"], weights=[7, 2, 1])[0]
                else:
                    ev.status = random.choices(
                        ["resuelto", "revisado", "nuevo"], weights=[5, 2, 3])[0]
                events.append(ev)
        db.session.add_all(events)
        db.session.commit()

        # --- Incidentes demo por empresa -----------------------------------
        incident_specs = [
            ("Acceso SSH sospechoso desde IP externa", "escalado", "critico"),
            ("Múltiples intentos de login a panel admin", "en_progreso", "aviso"),
            ("Revisión de certificado TLS próximo a expirar", "abierto", "aviso"),
            ("Malware bloqueado — análisis forense", "cerrado", "critico"),
        ]
        for company in clientes:
            crit_events = [e for e in events
                           if e.company_id == company.id and e.severity == "critico"]
            for idx, (title, status, sev) in enumerate(incident_specs):
                linked = crit_events[idx] if idx < len(crit_events) else None
                inc = Incident(
                    title=title,
                    description=f"Incidente demo de {company.name}. Severidad {sev}.",
                    severity=sev,
                    status=status,
                    company_id=company.id,
                    assignee_id=analyst.id if status != "abierto" else None,
                    event_id=linked.id if linked else None,
                    created_at=now - timedelta(hours=random.randint(2, 60)),
                )
                if status == "cerrado":
                    inc.closed_at = now - timedelta(hours=random.randint(1, 5))
                db.session.add(inc)
                db.session.flush()

                db.session.add(IncidentLog(
                    incident_id=inc.id, user_id=analyst.id, action="creado",
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

        # --- Notificación global de bienvenida -----------------------------
        db.session.add(Notification(
            kind="info", company_id=None,
            message="Bienvenido a SOC-PYME. Ejecutá `flask simulate` para ver eventos en vivo.",
        ))
        db.session.commit()

        # --- Resumen --------------------------------------------------------
        print("✅ Base de datos poblada (multi-empresa):")
        print(f"   Empresas     : {Company.query.count()}")
        print(f"   Usuarios     : {User.query.count()}")
        print(f"   Eventos      : {Event.query.count()}")
        print(f"   Incidentes   : {Incident.query.count()}")
        print(f"   Reglas alerta: {AlertRule.query.count()}")
        print(f"   Claves API   : {ApiKey.query.count()}")
        print()
        print("   Cuentas demo:")
        print("     👤 Cliente (Ferretería): demo@socpyme.co     / Demo1234!")
        print("     👤 Cliente (Panadería):  sofia@laespiga.co   / Espiga2026!")
        print("     🛡  Analista SOC (ve todo): julian@socpyme.co / Analista2026!")


if __name__ == "__main__":
    from app import create_app
    seed_database(create_app())
