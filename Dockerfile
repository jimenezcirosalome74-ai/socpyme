# SOC-PYME Solutions — imagen de producción
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FLASK_APP=app.py \
    FLASK_CONFIG=production

WORKDIR /app

# Dependencias primero (mejor cacheo de capas)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código
COPY . .

EXPOSE 8000

# Aplica migraciones y arranca el servidor WSGI (waitress)
CMD ["sh", "docker-entrypoint.sh"]
