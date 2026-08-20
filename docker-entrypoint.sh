#!/bin/sh
# Arranque del contenedor: aplica migraciones y levanta waitress.
set -e

echo "→ Aplicando migraciones de base de datos..."
flask db upgrade || echo "⚠ No se pudieron aplicar migraciones (¿BD ya inicializada?)."

# Sembrar datos demo solo si se pide explícitamente (SEED_DEMO=1)
if [ "$SEED_DEMO" = "1" ]; then
  echo "→ Sembrando datos demo..."
  python seed.py || echo "⚠ Seed omitido."
fi

echo "→ Iniciando SOC-PYME con waitress en :${PORT:-8000}"
exec waitress-serve --listen=0.0.0.0:${PORT:-8000} wsgi:app
