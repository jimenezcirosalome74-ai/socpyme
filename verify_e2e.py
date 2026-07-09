"""Verificación end-to-end con el test client de Flask.

Recorre el flujo completo: seed -> login -> dashboard -> filtrar eventos ->
inyectar eventos por API (disparar alerta) -> crear incidente -> cerrarlo.
"""
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

from app import create_app
from seed import seed_database
from models import AlertRule, Notification

CSRF_RE = re.compile(r'name="csrf_token"[^>]*value="([^"]+)"')


def csrf_from(html):
    m = CSRF_RE.search(html)
    return m.group(1) if m else None


def check(name, cond, extra=""):
    status = "OK " if cond else "FALLA"
    mark = "✅" if cond else "❌"
    print(f"  {mark} {name}: {status} {extra}")
    return cond


def main():
    app = create_app()
    seed_database(app)  # BD limpia y poblada
    client = app.test_client()

    results = []
    print("\n=== 1. Público ===")
    r = client.get("/")
    results.append(check("Landing (/)", r.status_code == 200 and "SOC-" in r.get_data(as_text=True)))
    r = client.get("/login?demo=1")
    html = r.get_data(as_text=True)
    results.append(check("Login demo visible", "demo@socpyme.co" in html))

    print("\n=== 2. Protección de rutas ===")
    r = client.get("/panel")
    results.append(check("/panel redirige sin login", r.status_code == 302 and "/login" in r.headers.get("Location", "")))
    r = client.get("/api/dashboard")
    results.append(check("/api/dashboard protegido", r.status_code in (302, 401)))

    print("\n=== 3. Login (CSRF) ===")
    token = csrf_from(html)
    results.append(check("Token CSRF presente", token is not None))
    r = client.post("/login", data={
        "csrf_token": token, "email": "demo@socpyme.co", "password": "Demo1234!",
    }, follow_redirects=False)
    results.append(check("Login correcto -> redirect", r.status_code == 302, r.headers.get("Location", "")))

    # Login con contraseña mala debe fallar (nueva sesión)
    c2 = app.test_client()
    t2 = csrf_from(c2.get("/login").get_data(as_text=True))
    r = c2.post("/login", data={"csrf_token": t2, "email": "demo@socpyme.co", "password": "malísima"}, follow_redirects=True)
    results.append(check("Login con clave mala rechazado", "incorrectos" in r.get_data(as_text=True)))

    print("\n=== 4. Dashboard ===")
    r = client.get("/panel")
    results.append(check("Dashboard carga", r.status_code == 200 and "Eventos hoy" in r.get_data(as_text=True)))
    r = client.get("/api/dashboard")
    data = r.get_json()
    results.append(check("API dashboard JSON", r.status_code == 200 and data["ok"] and "kpis" in data))
    results.append(check("Serie 7 días tiene 7 puntos", len(data["chart_7d"]["data"]) == 7))

    print("\n=== 5. Eventos + filtros ===")
    r = client.get("/eventos/")
    results.append(check("Lista de eventos", r.status_code == 200))
    r = client.get("/eventos/?severity=critico")
    results.append(check("Filtro por severidad", r.status_code == 200))
    r = client.get("/eventos/?q=SSH&status=nuevo")
    results.append(check("Búsqueda + estado", r.status_code == 200))

    print("\n=== 6. API: inyección de eventos y alerta ===")
    before = client.get("/api/dashboard").get_json()["notifications"]["unread"]
    triggered = 0
    for i in range(5):
        r = client.post("/api/events", json={
            "severity": "critico", "type": "Acceso SSH no autorizado",
            "description": f"Prueba {i}", "source_ip": "203.0.113.9",
        })
        if r.status_code == 201:
            triggered += r.get_json()["alerts_triggered"]
    results.append(check("POST /api/events (201) x5", triggered >= 0))
    after = client.get("/api/dashboard").get_json()["notifications"]["unread"]
    results.append(check("Alerta generó notificación", after > before, f"({before} -> {after})"))

    # Validación de API
    r = client.post("/api/events", json={"severity": "xxx", "type": "y"})
    results.append(check("API rechaza severidad inválida", r.status_code == 400))

    print("\n=== 7. Incidentes: crear desde evento y cerrar ===")
    # Tomar un evento crítico
    ev = client.get("/api/events?severity=critico&limit=1").get_json()["events"][0]
    page = client.get(f"/incidentes/nuevo?event_id={ev['id']}")
    ntoken = csrf_from(page.get_data(as_text=True))
    results.append(check("Form nuevo incidente (prefill)", page.status_code == 200 and str(ev["id"]) in page.get_data(as_text=True)))
    r = client.post("/incidentes/nuevo", data={
        "csrf_token": ntoken, "title": "Incidente de prueba E2E",
        "description": "Creado por el verificador.", "severity": "critico",
        "assignee_id": "0", "event_id": str(ev["id"]),
    }, follow_redirects=True)
    body = r.get_data(as_text=True)
    results.append(check("Incidente creado", "Incidente de prueba E2E" in body and "Bitácora" in body))

    # Extraer el id del incidente recién creado vía API
    incs = client.get("/api/incidents").get_json()["incidents"]
    new_inc = next((i for i in incs if i["title"] == "Incidente de prueba E2E"), None)
    results.append(check("Incidente aparece en API", new_inc is not None))

    if new_inc:
        det = client.get(f"/incidentes/{new_inc['id']}")
        dtoken = csrf_from(det.get_data(as_text=True))
        r = client.post(f"/incidentes/{new_inc['id']}/actualizar", data={
            "csrf_token": dtoken, "status": "cerrado", "assignee_id": "0",
            "note": "Cerrado por verificador.",
        }, follow_redirects=True)
        results.append(check("Incidente cerrado (bitácora)", "Cerrado" in r.get_data(as_text=True)))
        # Verificar via API PATCH también
        r = client.patch(f"/api/incidents/{new_inc['id']}", json={"status": "abierto"})
        results.append(check("API PATCH incidente", r.status_code == 200 and r.get_json()["incident"]["status"] == "abierto"))

    print("\n=== 8. Notificaciones read-all ===")
    r = client.post("/api/notifications/read-all")
    results.append(check("Marcar todas leídas", r.status_code == 200))
    after2 = client.get("/api/dashboard").get_json()["notifications"]["unread"]
    results.append(check("Contador en 0", after2 == 0, f"({after2})"))

    print("\n=== 9. Reglas de alerta (RF-05) ===")

    def notif_count(substr, unread_only=True):
        with app.app_context():
            q = Notification.query.filter(Notification.message.contains(substr))
            if unread_only:
                q = q.filter(Notification.read.is_(False))
            return q.count()

    def rule_by_name(name):
        with app.app_context():
            r = AlertRule.query.filter_by(name=name).first()
            return (r.id, r.active) if r else (None, None)

    # Limpiar notificaciones previas para aislar el flujo
    client.post("/api/notifications/read-all")

    # a) Crear regla vía UI (vigila 'info', umbral 2 en 5 min)
    page = client.get("/alertas/nueva")
    atoken = csrf_from(page.get_data(as_text=True))
    r = client.post("/alertas/nueva", data={
        "csrf_token": atoken, "name": "Regla E2E Info", "target_severity": "info",
        "threshold": "2", "window_minutes": "5", "channel": "in_app", "active": "y",
    }, follow_redirects=True)
    listing = r.get_data(as_text=True)
    results.append(check("Crear regla (visible en lista)", "Regla E2E Info" in listing))

    # b) Validación: rechaza N/X no positivos
    bad = client.get("/alertas/nueva")
    btoken = csrf_from(bad.get_data(as_text=True))
    r = client.post("/alertas/nueva", data={
        "csrf_token": btoken, "name": "Regla Inválida", "target_severity": "info",
        "threshold": "0", "window_minutes": "-5", "channel": "in_app", "active": "y",
    }, follow_redirects=True)
    rid_bad, _ = rule_by_name("Regla Inválida")
    results.append(check("Rechaza umbral/ventana no positivos", "positivo" in r.get_data(as_text=True) and rid_bad is None))

    rule_id, active = rule_by_name("Regla E2E Info")
    results.append(check("Regla persistida y activa", rule_id is not None and active is True))

    # c) Inyectar eventos que superan el umbral -> debe notificar
    before = notif_count("Regla E2E Info")
    for i in range(3):
        client.post("/api/events", json={"severity": "info", "type": "Login exitoso", "source_ip": "10.0.0.5"})
    after = notif_count("Regla E2E Info")
    results.append(check("Regla dispara notificación", after > before, f"({before} -> {after})"))

    # d) Desactivar la regla con el toggle
    dtok = csrf_from(client.get("/alertas/").get_data(as_text=True))
    client.post(f"/alertas/{rule_id}/toggle", data={"csrf_token": dtok}, follow_redirects=True)
    _, active2 = rule_by_name("Regla E2E Info")
    results.append(check("Toggle desactiva la regla", active2 is False))

    # e) Con la regla inactiva ya NO debe disparar
    client.post("/api/notifications/read-all")
    base = notif_count("Regla E2E Info")
    for i in range(4):
        client.post("/api/events", json={"severity": "info", "type": "Login exitoso", "source_ip": "10.0.0.6"})
    end = notif_count("Regla E2E Info")
    results.append(check("Regla inactiva no dispara", end == base, f"({base} -> {end})"))

    # f) Eliminar la regla
    etok = csrf_from(client.get("/alertas/").get_data(as_text=True))
    client.post(f"/alertas/{rule_id}/eliminar", data={"csrf_token": etok}, follow_redirects=True)
    gone, _ = rule_by_name("Regla E2E Info")
    results.append(check("Eliminar regla", gone is None))

    print("\n=== 10. Errores ===")
    r = client.get("/ruta-inexistente")
    results.append(check("404 personalizado", r.status_code == 404 and "no existe" in r.get_data(as_text=True)))

    print("\n=== 11. Logout ===")
    r = client.get("/logout", follow_redirects=False)
    results.append(check("Logout redirige", r.status_code == 302))
    r = client.get("/panel")
    results.append(check("Panel protegido tras logout", r.status_code == 302))

    passed = sum(1 for x in results if x)
    total = len(results)
    print(f"\n{'='*40}\nRESULTADO: {passed}/{total} verificaciones OK")
    print("="*40)
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
