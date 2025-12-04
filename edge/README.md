# Edge Layer

Maestro Modbus RTU con web UI para gestión de dispositivos, polling automático y publicación MQTT.

## Instalación

```bash
pip install -r requirements.txt
```

## Configuración

Editar `src/config.py`: puerto serie, baudrate, timeouts, MQTT broker

Opcional - ThingsBoard:
```bash
cp .env.example .env
# Editar ACCESS_TOKEN
```

## Ejecución

```bash
python src/app.py
```

Web UI: `http://localhost:5000`

## Interfaces

- **Dashboard**: Info adaptador RS-485
- **Configuración**: Discovery, identify, cambio UnitID/alias, umbrales
- **Polling**: Telemetría en tiempo real (WebSocket)

## Base de Datos

SQLite: `sensors`, `measurements`, `alerts`

## MQTT

ThingsBoard Gateway API:
- `v1/gateway/telemetry`
- `v1/gateway/attributes`
- `v1/gateway/rpc`
