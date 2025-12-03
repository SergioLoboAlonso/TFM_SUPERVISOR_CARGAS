# Integración MQTT - Plataformas IoT

Sistema de publicación MQTT para integración con plataformas IoT (ThingsBoard, FIWARE, AWS IoT, etc.).

## Arquitectura

```
Edge Layer (Python)
    ├── Polling Service → Lee telemetría Modbus
    ├── Alert Engine → Genera alertas
    └── MQTT Bridge → Publica a broker MQTT
            │
            ├── Medidas: edge/{device_id}/{sensor_type}/measurements
            └── Alertas: edge/{device_id}/alerts
```

## Configuración

Edita `.env`:

```bash
# MQTT Configuration
MQTT_BROKER_HOST=localhost          # IP/hostname del broker MQTT
MQTT_BROKER_PORT=1883              # Puerto (1883 por defecto)
MQTT_USERNAME=edge_user            # Usuario (opcional)
MQTT_PASSWORD=edge_pass            # Contraseña (opcional)
MQTT_QOS=1                         # QoS: 0, 1 o 2
MQTT_TOPIC_PREFIX=edge             # Prefijo de topics
```

## Estructura de Topics

### Medidas

**Topic:** `edge/{device_id}/{sensor_type}/measurements`

**Ejemplos:**
- `edge/unit_1/wind/measurements` - Velocidad del viento (WindMeter)
- `edge/unit_2/tilt/measurements` - Inclinación X/Y (MPU6050)
- `edge/unit_2/temperature/measurements` - Temperatura (MPU6050)
- `edge/unit_2/wind/measurements` - Velocidad del viento

**Payload:**
```json
{
  "timestamp": "2025-12-03T20:33:05.336267Z",
  "device_id": "unit_2",
  "sensor_id": "UNIT_2_TILT_X",
  "sensor_type": "tilt",
  "value": -0.46,
  "unit": "deg",
  "quality": "GOOD"
}
```

### Alertas

**Topic:** `edge/{device_id}/alerts`

**Ejemplos:**
- `edge/unit_2/alerts` - Alertas del dispositivo Unit 2
- `edge/system/alerts` - Alertas del sistema

**Payload:**
```json
{
  "timestamp": "2025-12-03T20:30:00.000000Z",
  "alert_id": 123,
  "device_id": "unit_2",
  "sensor_id": "UNIT_2_TILT_X",
  "level": "ALARM",
  "code": "THRESHOLD_EXCEEDED_HI",
  "message": "Sensor UNIT_2_TILT_X: valor 6.2 deg supera umbral superior 5.0 deg",
  "ack": false
}
```

## Instalación del Broker

### Opción 1: Mosquitto Local

```bash
# Instalar Mosquitto
sudo apt-get install -y mosquitto mosquitto-clients

# Verificar estado
sudo systemctl status mosquitto

# Ver logs
sudo journalctl -u mosquitto -f
```

### Opción 2: Docker Compose

```bash
cd /home/edge_sergio/Desktop/TFM_SUPERVISOR_CARGAS/infra
docker compose up -d mqtt
```

## Uso

### Suscribirse a Topics (Debugging)

```bash
# Ver TODAS las medidas y alertas
mosquitto_sub -h localhost -t "edge/#" -v

# Ver solo medidas de un dispositivo
mosquitto_sub -h localhost -t "edge/unit_2/+/measurements" -v

# Ver solo alertas
mosquitto_sub -h localhost -t "edge/+/alerts" -v

# Ver solo inclinación
mosquitto_sub -h localhost -t "edge/unit_2/tilt/measurements" -v
```

### Publicar Test (Opcional)

```bash
# Publicar medida de prueba
mosquitto_pub -h localhost -t "edge/test/temperature/measurements" \
  -m '{"timestamp":"2025-12-03T20:00:00Z","value":25.5,"unit":"celsius"}'
```

## Integración con Plataformas IoT

### ThingsBoard

1. Crear dispositivo en ThingsBoard con tipo "MQTT"
2. Copiar Access Token
3. Configurar `.env`:
   ```bash
   MQTT_BROKER_HOST=demo.thingsboard.io
   MQTT_BROKER_PORT=1883
   MQTT_USERNAME=<ACCESS_TOKEN>
   MQTT_QOS=1
   ```

### FIWARE IoT Agent

1. Desplegar IoT Agent MQTT
2. Registrar dispositivos con IDs `unit_1`, `unit_2`
3. Mapear attributes:
   - `tilt` → Inclinación
   - `temperature` → Temperatura
   - `wind` → Velocidad del viento

### AWS IoT Core

1. Crear "Thing" en AWS IoT
2. Descargar certificados
3. Configurar paho-mqtt con TLS

## QoS (Quality of Service)

- **QoS 0** (At most once): Sin confirmación, rápido pero puede perder mensajes
- **QoS 1** (At least once): Confirmado, puede haber duplicados (⭐ recomendado)
- **QoS 2** (Exactly once): Sin duplicados, más lento

## Logs

Ver actividad MQTT del Edge Service:

```bash
# Ver logs del servicio
journalctl -u tfm-edge.service -f | grep -i mqtt

# Ver conexión MQTT
journalctl -u tfm-edge.service -f | grep "Conectado a broker"

# Ver publicaciones
journalctl -u tfm-edge.service -f | grep "publicada"
```

## Troubleshooting

### MQTT no se conecta

1. Verificar broker activo:
   ```bash
   sudo systemctl status mosquitto
   ```

2. Verificar configuración en `.env`:
   ```bash
   cat .env | grep MQTT
   ```

3. Verificar logs:
   ```bash
   journalctl -u tfm-edge.service -n 50 | grep -i mqtt
   ```

### No llegan mensajes

1. Verificar topics con mosquitto_sub:
   ```bash
   mosquitto_sub -h localhost -t "#" -v
   ```

2. Verificar QoS en `.env`

3. Verificar firewall si broker es remoto:
   ```bash
   sudo ufw allow 1883/tcp
   ```

## Persistencia

- **Base de datos SQLite**: Todas las medidas se guardan en `edge.db`
- **MQTT**: Publicación en tiempo real (no persiste en broker por defecto)
- **Retención**: Configurar `mosquitto.conf` con `retain true` si necesario

## Estadísticas

Ver estadísticas de publicación:

```bash
# Contar mensajes publicados (últimos 5 min)
journalctl -u tfm-edge.service --since "5 minutes ago" | grep "Mensaje MQTT publicado" | wc -l

# Ver ratio de publicación
watch -n 5 'mosquitto_sub -h localhost -t "edge/#" -C 10 | wc -l'
```

## Roadmap

- [ ] Soporte TLS/SSL para brokers remotos
- [ ] Bridge automático a múltiples brokers
- [ ] Compresión de payloads (opcional)
- [ ] Agregación de medidas (reducir tráfico)
- [x] Auto-resolución de alertas vía MQTT
- [x] Publicación de medidas en tiempo real
- [x] Publicación de alertas

---

**Autor:** Sergio Lobo  
**Fecha:** 2025-12-03  
**Sistema:** Edge Layer - TFM Supervisor de Cargas
