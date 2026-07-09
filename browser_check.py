"""Verificación en navegador real: login, dashboard, charts, polling, notificaciones."""
import sys
from playwright.sync_api import sync_playwright

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

BASE = "http://127.0.0.1:5000"
OUT = r"C:\Users\HP\AppData\Local\Temp\claude\c--Users-HP-Desktop-socpyme\16ff5d6c-c1a7-43f5-82ff-39f83351a2d6\scratchpad"

errors = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.on("console", lambda m: errors.append(f"[{m.type}] {m.text}") if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(f"[pageerror] {e}"))

    # Landing
    page.goto(BASE, wait_until="networkidle")
    print("Landing title:", page.title())
    page.screenshot(path=OUT + r"\01_landing.png", full_page=True)

    # Login demo
    page.goto(BASE + "/login?demo=1", wait_until="networkidle")
    page.fill('input[name="email"]', "demo@socpyme.co")
    page.fill('input[name="password"]', "Demo1234!")
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")
    print("Después de login, URL:", page.url)

    # Dashboard — esperar a que Chart.js dibuje
    page.wait_for_timeout(1500)
    page.screenshot(path=OUT + r"\02_dashboard.png", full_page=True)

    # ¿Se renderizaron los canvas de Chart.js?
    charts = page.evaluate("""() => {
        const ids = ['chart7d', 'chartSeverity'];
        return ids.map(id => {
            const c = document.getElementById(id);
            return c ? {id, w: c.width, h: c.height} : {id, missing: true};
        });
    }""")
    print("Charts:", charts)

    kpi_events = page.text_content("#kpi-events")
    print("KPI eventos hoy:", kpi_events)

    # Campanita
    page.click("#bell-btn", timeout=5000)
    page.wait_for_timeout(400)
    bell_open = page.locator("#bell-dropdown.open").count() == 1
    print("Dropdown notificaciones abierto:", bell_open)
    page.screenshot(path=OUT + r"\03_notifications.png")

    # Eventos
    page.goto(BASE + "/eventos/", wait_until="networkidle")
    rows = page.locator("table.data-table tbody tr").count()
    print("Filas en lista de eventos:", rows)
    page.screenshot(path=OUT + r"\04_events.png", full_page=True)

    # Incidentes
    page.goto(BASE + "/incidentes/", wait_until="networkidle")
    inc_rows = page.locator("table.data-table tbody tr").count()
    print("Filas en incidentes:", inc_rows)
    page.screenshot(path=OUT + r"\05_incidents.png", full_page=True)

    # Detalle de incidente (primero)
    page.locator("table.data-table tbody tr").first.click()
    page.wait_for_load_state("networkidle")
    page.screenshot(path=OUT + r"\06_incident_detail.png", full_page=True)
    print("Detalle incidente URL:", page.url)

    browser.close()

print("\nErrores de consola/JS:", errors if errors else "NINGUNO ✅")
sys.exit(1 if errors else 0)
