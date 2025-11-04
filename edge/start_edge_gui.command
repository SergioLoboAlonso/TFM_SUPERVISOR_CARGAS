#!/bin/bash
# -----------------------------------------------------------------------------
# start_edge_gui.command - Launcher con GUI para Edge Layer
# Doble clic para arrancar, selección de modo debug, auto-reload en cambios
# -----------------------------------------------------------------------------

cd "$(dirname "$0")"

# Colores para el terminal
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║       TFM Supervisor de Cargas - Edge Layer Launcher      ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Verificar Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Error: Python3 no encontrado${NC}"
    echo "Instala Python 3.8+ desde https://www.python.org"
    read -p "Presiona ENTER para salir..."
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo -e "${GREEN}✓${NC} Python encontrado: ${PYTHON_VERSION}"

# Verificar dependencias
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}⚠ Entorno virtual no encontrado. Creando...${NC}"
    python3 -m venv venv
    source venv/bin/activate
    pip install -q --upgrade pip
    pip install -q -r requirements.txt
    echo -e "${GREEN}✓${NC} Dependencias instaladas"
else
    source venv/bin/activate
fi

echo ""
echo -e "${BLUE}Selecciona el modo de ejecución:${NC}"
echo ""
echo "  1) Producción (sin debug, sin auto-reload)"
echo "  2) Debug (debug mode ON, sin auto-reload)"
echo "  3) Desarrollo (debug mode ON, auto-reload en cambios)"
echo ""
read -p "Opción [1-3]: " MODE_CHOICE

case $MODE_CHOICE in
    1)
        echo -e "${GREEN}▶ Modo: Producción${NC}"
        DEBUG_MODE="0"
        AUTO_RELOAD=""
        ;;
    2)
        echo -e "${YELLOW}▶ Modo: Debug${NC}"
        DEBUG_MODE="1"
        AUTO_RELOAD=""
        ;;
    3)
        echo -e "${BLUE}▶ Modo: Desarrollo (auto-reload)${NC}"
        DEBUG_MODE="1"
        AUTO_RELOAD="--reload"
        ;;
    *)
        echo -e "${RED}Opción no válida. Usando modo Producción.${NC}"
        DEBUG_MODE="0"
        AUTO_RELOAD=""
        ;;
esac

echo ""
echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}   Iniciando Edge Layer...${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  Puerto serie: ${BLUE}/dev/tty.usbmodem5A300455411${NC}"
echo -e "  Baudrate:     ${BLUE}115200${NC}"
echo -e "  Web UI:       ${GREEN}http://192.168.0.23:8080${NC}"
echo -e "  Debug:        ${YELLOW}$([ "$DEBUG_MODE" = "1" ] && echo "ON" || echo "OFF")${NC}"
echo -e "  Auto-reload:  ${YELLOW}$([ -n "$AUTO_RELOAD" ] && echo "ON" || echo "OFF")${NC}"
echo ""
echo -e "${YELLOW}Presiona CTRL+C para detener el servidor${NC}"
echo ""

# Configurar variable de entorno para debug
export FLASK_DEBUG=$DEBUG_MODE

# Arrancar servidor con o sin auto-reload
if [ -n "$AUTO_RELOAD" ]; then
    # Modo desarrollo con watchdog para auto-reload
    python3 src/app.py --reload
else
    # Modo producción o debug sin auto-reload
    python3 src/app.py
fi

# Mantener terminal abierto en caso de error
if [ $? -ne 0 ]; then
    echo ""
    echo -e "${RED}❌ El servidor terminó con errores${NC}"
    read -p "Presiona ENTER para salir..."
fi
