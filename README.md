# SOC-PYME Solutions 🛡️

Plataforma de ciberseguridad (mini-SOC) para PYMES de Latinoamérica. Monitoreá
eventos de seguridad en tiempo real, detectá amenazas, gestioná incidentes y
recibí alertas cuando se superan umbrales configurables.

Construida con **Flask + SQLAlchemy + Flask-Login** y una interfaz "corporate
clean" (Inter + DM Mono, paleta navy/cyan/blue) con gráficos **Chart.js**.

---

## ✨ Funcionalidades

- **Landing page** pública responsive con animaciones `reveal`.
- **Autenticación** con registro, login/logout, contraseñas hasheadas (Werkzeug)
  y protección **CSRF** (Flask-WTF).
- **Dashboard en tiempo real** (RF-06): KPIs, gráfico de 7 días, dona por
  severidad y últimos 10 eventos, con **polling cada 10 s** vía `fetch()`.
- **Eventos de seguridad**: lista con filtros (severidad, estado, fechas),
  búsqueda por texto y paginación; detalle con cambio de estado.
- **Gestión de incidentes** (RF-07): CRUD completo, asignación, escalado,
  cierre y **bitácora de cambios** (`IncidentLog`) para trazabilidad.
- **Alertas** (RF-05): pantalla `/alertas` para **configurar reglas** (crear,
  editar, activar/desactivar con toggle y eliminar con confirmación), con umbral
  N de eventos en ventana de X minutos y canal de notificación. Los cambios
  quedan en una **bitácora de auditoría**. Al superarse un umbral se genera una
  **notificación** en la campanita del topbar.
- **API REST JSON** para inyección externa de eventos y consumo de datos.
- **Simulador** de eventos realistas para demostrar el tiempo real.
- Páginas de error **404 / 500** personalizadas.

---

## 🚀 Instalación

Requiere **Python 3.11+** (probado en 3.14).

```bash
# 1. Clonar / entrar a la carpeta
cd soc-pyme

# 2. Crear y activar entorno virtual
python -m venv venv
# Windows (PowerShell)
.\venv\Scripts\Activate.ps1
# Linux / macOS
source venv/bin/activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Poblar la base de datos con datos demo
python seed.py

# 5. Levantar la aplicación
#    (o bien: python app.py)
set FLASK_APP=app.py        # Windows CMD
$env:FLASK_APP="app.py"     # Windows PowerShell
export FLASK_APP=app.py     # Linux / macOS
flask run
```

La app queda disponible en **http://localhost:5000**.

---

## 🔑 Credenciales demo

| Rol      | Email               | Contraseña   |
|----------|---------------------|--------------|
| Cliente  | `demo@socpyme.co`   | `Demo1234!`  |
| Analista | `julian@socpyme.co` | `Analista2026!` |

Desde la landing, el botón **"Ver demo en vivo"** lleva al login con estas
credenciales visibles.

---

## ⚡ Simulador de eventos

Genera eventos aleatorios realistas para ver el dashboard actualizarse solo y
disparar alertas:

```bash
flask simulate                    # infinito, un evento cada 3 s (Ctrl+C para parar)
flask simulate --interval 1       # más rápido
flask simulate --count 20         # genera 20 eventos y termina
```

Dejá `flask run` corriendo en una terminal y `flask simulate` en otra: verás los
KPIs, gráficos y la campanita de notificaciones actualizarse en vivo.

---

## 🌐 API REST

Todas las respuestas son JSON con `"ok": true|false` y códigos HTTP correctos.
Los endpoints de lectura del panel requieren sesión; **`POST /api/events` es
público** para permitir que sistemas externos inyecten eventos.

### Inyectar un evento (sistemas externos)

```bash
curl -X POST http://localhost:5000/api/events \
  -H "Content-Type: application/json" \
  -d '{
        "severity": "critico",
        "type": "Acceso SSH no autorizado",
        "description": "Intento al puerto 22",
        "source_ip": "203.0.113.9"
      }'
```

Respuesta `201`:
```json
{ "ok": true, "event": { "...": "..." }, "alerts_triggered": 1 }
```

### Otros endpoints

| Método | Ruta                               | Descripción                          |
|--------|------------------------------------|--------------------------------------|
| GET    | `/api/dashboard`                   | KPIs, series de gráficos y notifs    |
| GET    | `/api/events?severity=critico`     | Lista de eventos (con filtros)       |
| POST   | `/api/events`                      | Inyección de evento (público)        |
| GET    | `/api/incidents?status=abierto`    | Lista de incidentes                  |
| POST   | `/api/incidents`                   | Crear incidente                      |
| PATCH  | `/api/incidents/<id>`              | Actualizar estado/asignación         |
| POST   | `/api/notifications/read-all`      | Marcar notificaciones como leídas    |

Ejemplo de consulta:
```bash
curl http://localhost:5000/api/events?severity=critico&limit=5
```

---

## 🗂️ Estructura del proyecto

```
soc-pyme/
├── app.py               # App factory + CLI (simulate, seed) + error handlers
├── config.py            # SECRET_KEY, DB, cookies seguras, parámetros
├── extensions.py        # db, login_manager, csrf
├── models.py            # User, Event, Incident, IncidentLog, AlertRule, AuditLog, Notification
├── forms.py             # Formularios WTForms (validación + CSRF)
├── services.py          # Lógica: evaluación de alertas, KPIs, bitácora
├── seed.py              # Datos demo realistas
├── simulator.py         # Generador de eventos (flask simulate)
├── requirements.txt
├── routes/
│   ├── main.py          # Landing / páginas públicas
│   ├── auth.py          # Registro, login, logout
│   ├── dashboard.py     # Panel principal
│   ├── events.py        # Eventos: lista, filtros, detalle
│   ├── incidents.py     # Incidentes: CRUD + bitácora
│   ├── alerts.py        # Reglas de alerta: CRUD + toggle + bitácora (RF-05)
│   └── api.py           # API REST JSON
├── templates/
│   ├── base.html            # Layout público
│   ├── base_app.html        # Layout del panel (sidebar + topbar + campanita)
│   ├── index.html           # Landing
│   ├── auth/                # login.html, register.html
│   ├── dashboard/           # index.html
│   ├── events/              # list.html, detail.html
│   ├── incidents/           # list.html, detail.html, new.html
│   ├── alerts/              # list.html, form.html
│   └── errors/              # 404.html, 500.html
└── static/
    ├── css/  (main.css, dashboard.css)
    └── js/   (main.js, dashboard.js)
```

---

## 🔒 Seguridad

- Contraseñas hasheadas con Werkzeug (`generate_password_hash`).
- Protección **CSRF** en todos los formularios (Flask-WTF); la API JSON se exime
  explícitamente por diseño.
- Cookies de sesión `HttpOnly` + `SameSite=Lax` (y `Secure` en producción).
- Todas las rutas del panel protegidas con `@login_required`.
- Validación de entradas en cliente **y** servidor; protección contra
  open-redirect en el `next` del login.

Para producción, definí una `SECRET_KEY` real y activá cookies seguras:
```bash
export SECRET_KEY="una-clave-larga-y-aleatoria"
export SESSION_COOKIE_SECURE=1
export FLASK_CONFIG=production
```

---

## 🧪 Verificación

El repo incluye dos scripts de prueba (opcionales, requieren la app corriendo
solo para `browser_check.py`):

```bash
python verify_e2e.py       # 33 checks end-to-end con el test client de Flask
python browser_check.py    # verificación en navegador (requiere: pip install playwright)
```

---

## 🎨 Flujo de demostración sugerido

1. Abrí la **landing** → "Comenzar gratis" → **registrá** una cuenta (o usá la demo).
2. Entrás al **dashboard**: KPIs, gráficos y últimos eventos.
3. En otra terminal corré `flask simulate` y mirá cómo se actualiza solo.
4. Andá a **Eventos**, filtrá por *Crítico* y abrí uno.
5. "**Crear incidente**" desde el evento → asignalo → cambiá su estado.
6. **Cerralo** y revisá la **bitácora** de cambios.
7. Entrá a **Alertas** y creá una regla (ej: 3 eventos *Crítico* en 5 min).
   Activala/desactivala con el toggle o eliminala.
8. Mirá la **campanita** 🔔: cuando el simulador supera un umbral, la alerta
   aparece ahí.

© 2026 SOC-PYME Solutions · Medellín, Colombia
