#!/bin/bash

# Monitor nocturno de dispositivos Modbus RTU
# Registra estadísticas cada 5 minutos durante toda la noche

LOG_DIR="./logs"
LOG_FILE="${LOG_DIR}/overnight_monitor_$(date +%Y%m%d_%H%M%S).log"

# Crear directorio de logs si no existe
mkdir -p "${LOG_DIR}"

echo "==================================================================" | tee -a "${LOG_FILE}"
echo "Monitor nocturno iniciado: $(date)" | tee -a "${LOG_FILE}"
echo "==================================================================" | tee -a "${LOG_FILE}"
echo "" | tee -a "${LOG_FILE}"

# Función para registrar estadísticas
log_stats() {
    local timestamp=$(date "+%Y-%m-%d %H:%M:%S")
    
    echo "────────────────────────────────────────────────────────────────" >> "${LOG_FILE}"
    echo "Timestamp: ${timestamp}" >> "${LOG_FILE}"
    echo "────────────────────────────────────────────────────────────────" >> "${LOG_FILE}"
    
    # Arduino Uno (UnitID 2)
    echo "" >> "${LOG_FILE}"
    echo "📊 ARDUINO UNO (UnitID=2):" >> "${LOG_FILE}"
    curl -s http://localhost:8080/api/diagnostics/2 | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    stats = data.get('modbus_stats', {})
    print(f\"  ✅ RX OK:        {stats.get('rx_ok', 0):>8,}\")
    print(f\"  ✅ TX OK:        {stats.get('tx_ok', 0):>8,}\")
    print(f\"  ❌ CRC errors:   {stats.get('crc_errors', 0):>8,}\")
    print(f\"  ⚠️  UART overruns:{stats.get('uart_overruns', 0):>8,}\")
    print(f\"  ⏱️  Uptime:       {data.get('uptime_seconds', 0):>8,} sec\")
    
    # Calcular tasas
    uptime = data.get('uptime_seconds', 1)
    if uptime > 0:
        rx_rate = stats.get('rx_ok', 0) / uptime
        crc_rate = stats.get('crc_errors', 0) / uptime
        overrun_rate = stats.get('uart_overruns', 0) / uptime
        print(f\"  📈 RX rate:      {rx_rate:>8.2f} msg/s\")
        print(f\"  📈 CRC rate:     {crc_rate:>8.4f} err/s\")
        print(f\"  📈 Overrun rate: {overrun_rate:>8.4f} err/s\")
except Exception as e:
    print(f\"  ❌ Error: {e}\")
" >> "${LOG_FILE}"
    
    # Arduino Micro (UnitID 16)
    echo "" >> "${LOG_FILE}"
    echo "📊 ARDUINO MICRO (UnitID=16):" >> "${LOG_FILE}"
    curl -s http://localhost:8080/api/diagnostics/16 | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    stats = data.get('modbus_stats', {})
    print(f\"  ✅ RX OK:        {stats.get('rx_ok', 0):>8,}\")
    print(f\"  ✅ TX OK:        {stats.get('tx_ok', 0):>8,}\")
    print(f\"  ❌ CRC errors:   {stats.get('crc_errors', 0):>8,}\")
    print(f\"  ⚠️  UART overruns:{stats.get('uart_overruns', 0):>8,}\")
    print(f\"  ⏱️  Uptime:       {data.get('uptime_seconds', 0):>8,} sec\")
    
    # Calcular tasas
    uptime = data.get('uptime_seconds', 1)
    if uptime > 0:
        rx_rate = stats.get('rx_ok', 0) / uptime
        crc_rate = stats.get('crc_errors', 0) / uptime
        overrun_rate = stats.get('uart_overruns', 0) / uptime
        print(f\"  📈 RX rate:      {rx_rate:>8.2f} msg/s\")
        print(f\"  📈 CRC rate:     {crc_rate:>8.4f} err/s\")
        print(f\"  📈 Overrun rate: {overrun_rate:>8.4f} err/s\")
except Exception as e:
    print(f\"  ❌ Error: {e}\")
" >> "${LOG_FILE}"
    
    echo "" >> "${LOG_FILE}"
}

# Registro inicial
log_stats

# Intervalo de monitoreo: 5 minutos = 300 segundos
INTERVAL=300

echo "Monitor ejecutándose. Registrando cada ${INTERVAL}s..." | tee -a "${LOG_FILE}"
echo "Log: ${LOG_FILE}" | tee -a "${LOG_FILE}"
echo "Presiona Ctrl+C para detener." | tee -a "${LOG_FILE}"
echo "" | tee -a "${LOG_FILE}"

# Contador de iteraciones
COUNT=1

# Loop infinito
while true; do
    sleep ${INTERVAL}
    
    echo "=== Lectura #${COUNT} ===" >> "${LOG_FILE}"
    log_stats
    
    # Mostrar resumen en consola cada 30 minutos (6 iteraciones)
    if (( COUNT % 6 == 0 )); then
        echo "$(date): ${COUNT} lecturas completadas ($(( COUNT * INTERVAL / 60 )) minutos)"
    fi
    
    COUNT=$((COUNT + 1))
done
