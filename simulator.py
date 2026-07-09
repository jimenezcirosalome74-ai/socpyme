"""Simulador de eventos de seguridad realistas.

Uso:
    flask simulate                 # infinito, cada 3s
    flask simulate --interval 1    # más rápido
    flask simulate --count 20      # 20 eventos y termina
"""
import random
import sys
import time

# Consola UTF-8 en Windows (evita UnicodeEncodeError con emojis/acentos)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

from extensions import db
from models import Event
from services import evaluate_alerts

# Plantillas realistas: (severidad, tipo, plantilla_descripcion)
EVENT_TEMPLATES = [
    ("critico", "Acceso SSH no autorizado", "Intento de acceso al puerto 22 desde {ip}"),
    ("critico", "Malware detectado", "Firma de ransomware bloqueada en host-{host}"),
    ("critico", "Exfiltración de datos", "Transferencia inusual de {mb}MB hacia {ip}"),
    ("critico", "Escalada de privilegios", "Usuario 'svc-app' obtuvo permisos root en host-{host}"),
    ("critico", "Inyección SQL", "Patrón de SQLi detectado en /api/login desde {ip}"),
    ("aviso", "Intentos de login fallidos", "{n} intentos fallidos para 'admin' desde {ip}"),
    ("aviso", "Puerto inusual abierto", "Puerto {port} abierto en host-{host}"),
    ("aviso", "Certificado por expirar", "El certificado TLS de api.pyme.co expira en {n} días"),
    ("aviso", "Tráfico anómalo", "Pico de tráfico saliente detectado en host-{host}"),
    ("aviso", "Actualización pendiente", "Parche de seguridad crítico sin aplicar en host-{host}"),
    ("info", "Login exitoso", "Inicio de sesión de 'admin' desde {ip}"),
    ("info", "Backup completado", "Respaldo automático finalizado ({mb}MB)"),
    ("info", "Nuevo dispositivo", "Dispositivo host-{host} registrado en la red"),
    ("info", "Escaneo programado", "Análisis de vulnerabilidades completado sin hallazgos"),
    ("info", "Sesión cerrada", "Cierre de sesión de 'operador' desde {ip}"),
]

# Peso: más avisos/info que críticos (realista)
WEIGHTS = [t[0] for t in EVENT_TEMPLATES]
SEV_WEIGHT = {"critico": 1, "aviso": 3, "info": 4}


def _random_ip():
    return f"{random.randint(1,223)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"


def make_event():
    """Construye (sin persistir) un Event aleatorio realista."""
    template = random.choices(
        EVENT_TEMPLATES, weights=[SEV_WEIGHT[t[0]] for t in EVENT_TEMPLATES], k=1
    )[0]
    severity, event_type, desc_tpl = template
    ip = _random_ip()
    description = desc_tpl.format(
        ip=ip,
        host=random.randint(1, 40),
        n=random.randint(3, 12),
        mb=random.randint(5, 950),
        port=random.choice([21, 23, 445, 3389, 8080, 5432]),
    )
    return Event(
        severity=severity,
        event_type=event_type,
        description=description,
        source_ip=ip,
        status="nuevo",
    )


def run_simulator(app, interval=3.0, count=0):
    """Genera eventos periódicamente dentro del contexto de la app."""
    generated = 0
    click_msg = f"cada {interval}s" + (f", {count} eventos" if count else ", infinito (Ctrl+C para parar)")
    print(f"⚡ Simulador SOC-PYME iniciado ({click_msg}).")
    try:
        with app.app_context():
            while count == 0 or generated < count:
                event = make_event()
                db.session.add(event)
                db.session.commit()
                triggered = evaluate_alerts()
                generated += 1
                flag = "  🚨 ALERTA" if triggered else ""
                print(f"[{generated}] {event.severity_label:<8} {event.event_type} · {event.source_ip}{flag}")
                if count and generated >= count:
                    break
                time.sleep(interval)
    except KeyboardInterrupt:
        print(f"\n⏹ Simulador detenido. {generated} eventos generados.")


if __name__ == "__main__":
    # Permite `python simulator.py` sin flask CLI
    from app import create_app
    run_simulator(create_app())
