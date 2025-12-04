#!/bin/bash
# Script de inicio rápido para Edge CLI
# Activa el entorno virtual del edge y ejecuta la CLI

# Navegar al directorio del script
cd "$(dirname "$0")"

# Verificar que existe el venv del edge
VENV_PATH="../edge/venv"
if [ ! -d "$VENV_PATH" ]; then
    echo "❌ Error: No se encuentra el entorno virtual en $VENV_PATH"
    echo "ℹ️  Ejecuta primero: cd ../edge && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Activar entorno virtual
source "$VENV_PATH/bin/activate"

# Verificar que .env existe
if [ ! -f "../edge/.env" ]; then
    echo "⚠️  Advertencia: No existe ../edge/.env"
    echo "ℹ️  Copia el ejemplo: cp ../edge/.env.example ../edge/.env"
    echo ""
fi

# Ejecutar CLI
echo "🚀 Iniciando Edge CLI..."
python3 edge_cli.py "$@"

# Desactivar venv al salir
deactivate
