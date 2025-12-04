# Edge Layer - Supervisor de Cargas

Aplicación web para gestión y monitoreo de dispositivos Modbus RTU.

## 🚀 Optimización de Rendimiento

Discovery de dispositivos **89% más rápido** que la configuración por defecto:
- **100 UnitIDs**: ~19 segundos (vs ~180s original)
- **10 UnitIDs**: ~2-3 segundos (vs ~18s original)

Ver [`docs/PERFORMANCE_OPTIMIZATION.md`](../docs/PERFORMANCE_OPTIMIZATION.md) para detalles completos.

## Arquitectura

- **3 Ventanas principales**:
  - **Dashboard** (`/`): Info del adaptador USB-RS485
  - **Configuración** (`/config`): Discovery, identify, alias, cambio de UnitID
  - **Polling** (`/polling`): Telemetría en tiempo real con WebSocket

## Estructura del Proyecto

```
edge/
├── src/
│   ├── config.py           # Configuración global
│   ├── logger.py           # Logging estructurado
│   ├── modbus_client.py    # Cliente Modbus RTU (pymodbus wrapper)
│   ├── data_normalizer.py  # Conversión escalados → unidades físicas
│   ├── device_manager.py   # Discovery, caché de dispositivos
│   ├── polling_service.py  # Servicio de polling automático
│   ├── websocket_handler.py # WebSocket para telemetría en tiempo real
│   └── app.py              # Flask app principal
├── templates/
│   ├── dashboard.html
│   ├── config.html
│   └── polling.html
├── static/
│   ├── css/
│   │   └── style.css
│   └── js/
│       ├── dashboard.js
│       ├── config.js
│       └── polling.js
├── tests/
│   └── test_normalizer.py
├── requirements.txt
├── .env.example
└── README.md
```

## Instalación

1. **Crear entorno virtual**:
```bash
cd edge
python3 -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
```

2. **Instalar dependencias**:
```bash
pip install -r requirements.txt
```

3. **Configurar variables de entorno**:
```bash
cp .env.example .env
# Editar .env con tu configuración (puerto serie, baudrate, etc.)
```

## Configuración

Archivo `.env`:

```bash
# Puerto serie Modbus RTU (CONFIGURACIÓN MANUAL - sin autodetección)
# Especificar el puerto del adaptador RS-485
# MODBUS_PORT=/dev/ttyUSB0         # Linux/Raspberry Pi
# MODBUS_PORT=/dev/tty.usbserial-XXXXXXX  # macOS (adaptador USB-RS485)
MODBUS_BAUDRATE=115200
MODBUS_TIMEOUT=1.0

# Discovery
DEVICE_UNIT_ID_MIN=1
DEVICE_UNIT_ID_MAX=10

# Polling
POLL_INTERVAL_SEC=5.0
INTER_FRAME_DELAY_MS=50

# Flask app
FLASK_HOST=0.0.0.0
FLASK_PORT=8080
FLASK_DEBUG=True

# Logging
LOG_LEVEL=INFO
LOG_FILE=edge.log
```

## Ejecución

```bash
cd edge
source venv/bin/activate
python src/app.py
```

Navegar a: http://localhost:8080

## Uso

### 1. Dashboard
- Ver info del adaptador USB-RS485
- Estadísticas globales (tramas TX/RX, errores CRC)
- Navegar a Configuración o Polling

### 2. Configuración
- **Discovery**: Escanear red para descubrir dispositivos (UnitID 1..10)
- **Identify**: Hacer parpadear LED de dispositivo seleccionado
- **Editar Alias**: Cambiar alias de dispositivo y guardar a EEPROM
- **Cambiar UnitID**: Reasignar UnitID de dispositivo

### 3. Polling (Telemetría en Vivo)
- Seleccionar dispositivos a monitorear
- Configurar intervalo de polling (segundos)
- Ver telemetría en tiempo real:
  - Ángulos X/Y (°)
  - Temperatura (°C)
  - Aceleración X/Y/Z (g)
  - Giroscopio X/Y/Z (°/s)
  - Peso (kg)
  - Contador de muestras
- Log de eventos (timeouts, errores CRC, etc.)

## API REST

### Adaptador
- `GET /api/adapter` - Info del adaptador USB-RS485

### Dispositivos
- `POST /api/discover` - Ejecutar discovery (body: `{unit_id_min, unit_id_max}`)
- `GET /api/devices` - Lista de dispositivos en caché
- `GET /api/devices/{unit_id}` - Info de dispositivo específico
- `POST /api/devices/{unit_id}/identify` - Activar LED (body: `{duration_sec}`)
- `PUT /api/devices/{unit_id}/alias` - Guardar alias (body: `{alias}`)
- `PUT /api/devices/{unit_id}/unit_id` - Cambiar UnitID (body: `{new_unit_id}`)

### Polling
- `POST /api/polling/start` - Iniciar polling (body: `{interval_sec, unit_ids}`)
- `POST /api/polling/stop` - Detener polling
- `GET /api/polling/status` - Estado del polling
- `WebSocket /api/polling/stream` - Stream de telemetría en tiempo real

### Health
- `GET /api/health` - Estado del Edge (uptime, conexiones)

## Testing

```bash
pytest tests/
```

## Troubleshooting

### Identificar el puerto serie correcto (RS-485 vs Arduino)

**macOS:**
```bash
# Listar todos los puertos USB
ls /dev/tty.*

# Identificar cuál es el RS-485:
# 1. Desconectar SOLO el adaptador RS-485
# 2. Anotar puertos presentes
# 3. Reconectar RS-485
# 4. Ver qué puerto nuevo apareció → ese es el RS-485
```

**Linux:**
```bash
# Listar puertos
ls /dev/ttyUSB*

# Ver info detallada
dmesg | grep tty
# Buscar el adaptador RS-485 (ej. "FTDI", "CH340", "CP210x")
```

**Configuración**:
- Copiar el puerto del adaptador RS-485 a `.env`:
  ```bash
  MODBUS_PORT=/dev/tty.usbserial-XXXXXXX  # El del RS-485, NO el Arduino
  ```

### Puerto serie no detectado
```bash
# macOS/Linux: listar puertos disponibles
ls /dev/tty.*
ls /dev/ttyUSB*

# Permisos en Linux
sudo usermod -a -G dialout $USER
sudo chmod 666 /dev/ttyUSB0
```

### Timeout al leer dispositivos
- Verificar conexión física RS-485 (A, B, GND)
- Verificar baudrate coincide con firmware (115200)
- Verificar UnitID del dispositivo
- Aumentar `MODBUS_TIMEOUT` en `.env`

### Errores CRC
- Verificar cableado (colisiones, ruido)
- Aumentar `INTER_FRAME_DELAY_MS` en `.env`

## Licencia

MIT

## Autor

Sergio Lobo - TFM UNIR 2025
