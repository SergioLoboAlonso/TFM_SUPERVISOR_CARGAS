#!/bin/bash
# start_edge.sh - Iniciar servidor Edge Layer
# Uso: ./start_edge.sh

set -e

# Verificar entorno virtual
# Activar entorno virtual
if [ -d "../.venv" ]; then
    # venv en la raíz del repo
    source ../.venv/bin/activate
elif [ -d "venv" ]; then
    # venv local dentro de edge/
    source venv/bin/activate
else
    echo "❌ Error: No se encontró entorno virtual (.venv en raíz o venv en edge)."
    echo "Ejecuta: python3 -m venv ../.venv && source ../.venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Verificar archivo .env
if [ ! -f ".env" ]; then
    echo "⚠️  No se encontró edge/.env, copiando desde .env.example"
    cp .env.example .env
    echo "✏️  Edita edge/.env para fijar MODBUS_PORT al adaptador RS-485 correcto (no el Arduino)."
fi

# Iniciar servidor
echo "🚀 Iniciando Edge Layer Server..."
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
echo "📄 Usando configuración .env:" && grep -E "^(MODBUS_PORT|MODBUS_BAUDRATE|FLASK_PORT|DEVICE_UNIT_ID_MIN|DEVICE_UNIT_ID_MAX)=" .env || true
python3 src/app.py
