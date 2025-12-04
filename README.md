# Sistema de Supervisión y Monitoreo de Cargas

Sistema distribuido de adquisición de datos basado en Modbus RTU sobre RS-485. Nodos sensores (AVR) transmiten telemetría a capa Edge (Raspberry Pi) que publica datos mediante MQTT.

## Estructura

```
├── firmware/          # Firmware nodos sensores
├── edge/              # Aplicación Edge Layer
└── infra/             # Infraestructura opcional
```

## Requisitos

**Firmware:** PlatformIO, Arduino UNO/NANO, RS-485

**Edge:** Python 3.8+, USB-RS485, `pip install -r edge/requirements.txt`

## Ejecución

**Firmware:**
```bash
cd firmware && pio run -e uno -t upload
```

**Edge:**
```bash
cd edge && python src/app.py
```

Web UI: `http://localhost:5000`

## Configuración

- `firmware/platformio.ini` - Sensores y pines
- `edge/src/config.py` - Puerto serie, baudrate, MQTT
- `edge/.env` - Credenciales cloud (opcional)
