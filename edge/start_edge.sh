#!/bin/bash
# start_edge.sh - Iniciar servidor Edge Layer
# Uso: ./start_edge.sh

set -e

# Verificar entorno virtual
if [ ! -d "venv" ]; then
    echo "❌ Error: No se encontró el entorno virtual."
    echo "Ejecuta primero: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Activar entorno
source venv/bin/activate

# Verificar archivo .env
if [ ! -f ".env" ]; then
    echo "⚠️  Advertencia: No se encontró .env, copiando desde .env.example"
    cp .env.example .env
    echo "✏️  EDITA edge/.env con tu puerto RS-485 correcto antes de continuar"
    exit 1
fi

# Iniciar servidor
echo "🚀 Iniciando Edge Layer Server..."
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
python3 src/app.py
