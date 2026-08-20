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
  N de eventos en ventana de X minutos, canal y destino. Los cambios quedan en
  una **bitácora de auditoría**.
- **Entrega real de alertas**: al superarse un umbral, la alerta sale por su
  canal — **in-app** (campanita), **webhook** (POST JSON a una URL, funcional),
  **email** (SMTP; sin configurar, modo demo que registra el envío) y **SMS**
  (requiere proveedor). Cada intento se registra en `AlertDelivery` y se ve en el
  panel **"Entregas recientes"**.
- **Multi-tenancy + roles**: cada empresa (tenant) ve **solo sus** eventos,
  incidentes, alertas y notificaciones. Roles: `cliente`/`admin` (acotados a su
  empresa) y `analista` del SOC (ve **todas** las empresas). El registro crea una
  empresa nueva y deja al usuario como su administrador.
- **Claves API por empresa** (`/claves-api`): generá, activá/desactivá y eliminá
  claves. `POST /api/events` exige el header `X-API-Key` y asocia el evento a la
  empresa dueña de la clave.
- **Gestión de cuenta** (`/cuenta`): editar perfil, renombrar la empresa (admin),
  **cambiar contraseña**, y **recuperación de contraseña** (`/recuperar`) con
  token firmado y expirable. Los administradores gestionan los **usuarios de su
  empresa** (`/cuenta/usuarios`): invitar (con contraseña temporal), cambiar rol
  y eliminar.
- **API REST JSON** para inyección externa de eventos y consumo de datos.
- **Simulador** de eventos realistas (repartidos entre empresas) para el tiempo real.
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

| Rol | Empresa | Email | Contraseña |
|-----|---------|-------|------------|
| Admin (cliente) | Ferretería El Tornillo SAS | `demo@socpyme.co` | `Demo1234!` |
| Admin (cliente) | Panadería La Espiga SAS | `sofia@laespiga.co` | `Espiga2026!` |
| Analista SOC (ve todo) | SOC-PYME Solutions | `julian@socpyme.co` | `Analista2026!` |

Ingresá con **`demo@socpyme.co`** y con **`sofia@laespiga.co`**: cada uno ve
**solo los datos de su empresa**. Con **`julian@socpyme.co`** ves los datos de
**todas** las empresas (rol analista). Desde la landing, **"Ver demo en vivo"**
lleva al login con las credenciales del cliente visibles.

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
Los endpoints de lectura del panel requieren **sesión** y están acotados a la
empresa del usuario. **`POST /api/events` requiere una API key** (header
`X-API-Key`) y asocia el evento a la empresa dueña de la clave. Generá tus claves
en el panel → **Claves API** (`/claves-api`).

### Inyectar un evento (sistemas externos)

```bash
curl -X POST http://localhost:5000/api/events \
  -H "Content-Type: application/json" \
  -H "X-API-Key: socpyme_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" \
  -d '{
        "severity": "critico",
        "type": "Acceso SSH no autorizado",
        "description": "Intento al puerto 22",
        "source_ip": "203.0.113.9"
      }'
```

Respuesta `201`:
```json
{ "ok": true, "event": { "...": "..." }, "company_id": 2, "alerts_triggered": 1 }
```
Sin clave o con clave inválida devuelve `401`.

### Otros endpoints

| Método | Ruta                               | Auth       | Descripción                          |
|--------|------------------------------------|------------|--------------------------------------|
| GET    | `/api/dashboard`                   | sesión     | KPIs, gráficos y notifs (de tu empresa) |
| GET    | `/api/events?severity=critico`     | sesión     | Eventos de tu empresa (con filtros)  |
| POST   | `/api/events`                      | API key    | Inyección de evento                  |
| GET    | `/api/incidents?status=abierto`    | sesión     | Incidentes de tu empresa             |
| POST   | `/api/incidents`                   | sesión     | Crear incidente                      |
| PATCH  | `/api/incidents/<id>`              | sesión     | Actualizar estado/asignación         |
| POST   | `/api/notifications/read-all`      | sesión     | Marcar notificaciones como leídas    |

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
├── models.py            # Company, User(rol), Event, Incident, IncidentLog, AlertRule, AlertDelivery, AuditLog, Notification, ApiKey
├── delivery.py          # Entrega de alertas por canal (in-app, email SMTP, webhook, SMS)
├── forms.py             # Formularios WTForms (validación + CSRF)
├── services.py          # Lógica: evaluación de alertas, KPIs, bitácora
├── seed.py              # Datos demo realistas
├── simulator.py         # Generador de eventos (flask simulate)
├── wsgi.py / serve.py   # Punto de entrada WSGI + arranque con waitress
├── Dockerfile           # Imagen de producción (+ docker-entrypoint.sh)
├── migrations/          # Migraciones Alembic (Flask-Migrate)
├── .env.example         # Plantilla de variables de entorno
├── requirements.txt
├── routes/
│   ├── main.py          # Landing / páginas públicas
│   ├── auth.py          # Registro, login, logout
│   ├── dashboard.py     # Panel principal
│   ├── events.py        # Eventos: lista, filtros, detalle
│   ├── incidents.py     # Incidentes: CRUD + bitácora
│   ├── alerts.py        # Reglas de alerta: CRUD + toggle + bitácora (RF-05)
│   ├── apikeys.py       # Claves API por empresa (multi-tenancy)
│   ├── account.py       # Cuenta: perfil, contraseña, empresa y usuarios
│   └── api.py           # API REST JSON
├── templates/
│   ├── base.html            # Layout público
│   ├── base_app.html        # Layout del panel (sidebar + topbar + campanita)
│   ├── index.html           # Landing
│   ├── auth/                # login.html, register.html, forgot.html, reset.html
│   ├── dashboard/           # index.html
│   ├── events/              # list.html, detail.html
│   ├── incidents/           # list.html, detail.html, new.html
│   ├── alerts/              # list.html, form.html
│   ├── apikeys/             # index.html
│   ├── account/             # index.html, users.html
│   └── errors/              # 403.html, 404.html, 429.html, 500.html
└── static/
    ├── css/  (main.css, dashboard.css)
    └── js/   (main.js, dashboard.js)
```

---

## 🔒 Seguridad

- Contraseñas hasheadas con Werkzeug (`generate_password_hash`).
- Protección **CSRF** en todos los formularios (Flask-WTF); la API JSON se exime
  explícitamente por diseño.
- **Aislamiento por empresa (multi-tenancy)**: cada consulta se filtra por la
  empresa del usuario; el acceso directo por URL a datos de otra empresa devuelve
  404. El rol `analista` es el único con visión global.
- **Inyección de eventos autenticada** con API key por empresa (header `X-API-Key`).
- **Rate limiting** en login/registro/recuperación (anti fuerza bruta,
  Flask-Limiter) — configurable con `AUTH_RATELIMIT`.
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

**Envío real de emails de alerta** (opcional): definí las variables SMTP. Sin
ellas, los correos se registran en modo demo (visibles en «Entregas recientes»),
pero no se envían.
```bash
export SMTP_HOST=smtp.tu-proveedor.com
export SMTP_PORT=587
export SMTP_USER=usuario
export SMTP_PASSWORD=secreto
export MAIL_FROM="alertas@tu-dominio.com"
```
Los **webhooks** funcionan sin configuración: la regla hace un `POST` JSON a la
URL que definas.

---

## 🚢 Producción / Despliegue

**Servidor WSGI** (waitress, multiplataforma):
```bash
python serve.py                              # 0.0.0.0:8000
# o directamente:
waitress-serve --listen=0.0.0.0:8000 wsgi:app
```

**Migraciones de base de datos** (Flask-Migrate/Alembic). En producción el
esquema NO se crea solo: se aplica con migraciones (así los cambios de esquema
no obligan a re-sembrar).
```bash
export FLASK_APP=app.py
flask db upgrade                 # aplica las migraciones a la BD
# al cambiar los modelos:
flask db migrate -m "descripción del cambio"
flask db upgrade
```

**Variables de entorno**: copiá `.env.example` a `.env` y completá (se cargan
automáticamente con python-dotenv).

**Docker**:
```bash
docker build -t soc-pyme .
docker run -p 8000:8000 -e SECRET_KEY=xxxx -e SEED_DEMO=1 soc-pyme
```
El contenedor aplica migraciones y arranca waitress; con `SEED_DEMO=1` además
carga los datos demo.

---

## 🧪 Verificación

El repo incluye dos scripts de prueba (opcionales, requieren la app corriendo
solo para `browser_check.py`):

```bash
python verify_e2e.py       # 57 checks end-to-end (multi-tenancy, API keys, cuenta, alertas, rate limiting)
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
