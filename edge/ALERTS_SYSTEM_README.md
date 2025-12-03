# Sistema de Alertas - Edge Layer

## Descripción

Sistema automático de generación y gestión de alertas basado en:
- **Umbrales de sensores** (alarm_lo, alarm_hi)
- **Estado de dispositivos** (timeout de telemetría)
- **Persistencia en BD** (tabla alerts)
- **Notificaciones en tiempo real** (SocketIO)

## Arquitectura

```
PollingService (cada 2s)
    │
    ├─> Lectura Modbus → Medida
    │       │
    │       ├─> database.insert_measurement()
    │       └─> alert_engine.check_measurement_thresholds()
    │               │
    │               ├─> ¿Viola umbral? → database.insert_alert()
    │               └─> socketio.emit('new_alert')
    │
AlertEngine Thread (cada 10s)
    │
    └─> check_device_status()
            │
            ├─> ¿last_seen > 30s? → DEVICE_OFFLINE alert
            └─> socketio.emit('new_alert')
```

## Configuración de Umbrales

Los umbrales se configuran automáticamente al registrar sensores en discovery:

| Sensor | alarm_lo | alarm_hi | Descripción |
|--------|----------|----------|-------------|
| TILT_X, TILT_Y | -10.0° | +10.0° | Inclinación crítica |
| TEMP | -10.0°C | +60.0°C | Temperatura operativa |
| ACCEL | - | 2.0g | Aceleración anómala |
| GYRO | - | 250.0°/s | Velocidad angular excesiva |
| WIND_SPEED | - | 25.0 m/s | Viento fuerte (~90 km/h) |
| LOAD | -5.0 kg | 500.0 kg | Carga anómala/sobrecarga |

## Niveles de Alerta

- **INFO**: Informativo, no requiere acción
- **WARN**: Advertencia, revisar cuando sea posible
- **ALARM**: Alarma, requiere atención pronto
- **CRITICAL**: Crítico, requiere acción inmediata

## Códigos de Alerta

### Umbrales
- `THRESHOLD_EXCEEDED_HI`: Valor supera umbral superior
- `THRESHOLD_EXCEEDED_LO`: Valor por debajo de umbral inferior

### Dispositivos
- `DEVICE_OFFLINE`: Sin telemetría > 30 segundos

## API REST

### GET /api/alerts
Lista alertas con filtros opcionales.

**Query params:**
- `ack`: "true" (reconocidas) / "false" (activas) / omitir (todas)
- `level`: "INFO" / "WARN" / "ALARM" / "CRITICAL"
- `limit`: Número máximo (default: 100)

**Ejemplo:**
```bash
curl 'http://localhost:8080/api/alerts?ack=false&level=ALARM&limit=10'
```

**Response:**
```json
{
  "alerts": [
    {
      "id": 123,
      "timestamp": "2025-12-03T20:00:00Z",
      "sensor_id": "UNIT_2_TILT_X",
      "rig_id": "RIG_01",
      "level": "ALARM",
      "code": "THRESHOLD_EXCEEDED_HI",
      "message": "Sensor UNIT_2_TILT_X: valor 6.20 deg supera el umbral superior 5.00 deg",
      "ack": 0
    }
  ],
  "count": 1
}
```

### POST /api/alerts/<id>/acknowledge
Marca una alerta como reconocida.

**Ejemplo:**
```bash
curl -X POST http://localhost:8080/api/alerts/123/acknowledge
```

**Response:**
```json
{
  "success": true,
  "alert_id": 123,
  "message": "Alert acknowledged"
}
```

### GET /api/alerts/stats
Estadísticas de alertas.

**Ejemplo:**
```bash
curl http://localhost:8080/api/alerts/stats
```

**Response:**
```json
{
  "total_active": 15,
  "by_level": {
    "INFO": 2,
    "WARN": 5,
    "ALARM": 7,
    "CRITICAL": 1
  },
  "recent_count": 8
}
```

## WebSocket Events

### Cliente → Servidor
Ninguno (por ahora)

### Servidor → Cliente

#### new_alert
Emitido cuando se genera una alerta.

```javascript
socket.on('new_alert', (alert) => {
  console.log('Nueva alerta:', alert);
  // alert = {
  //   id: 123,
  //   level: 'ALARM',
  //   code: 'THRESHOLD_EXCEEDED_HI',
  //   message: '...',
  //   sensor_id: 'UNIT_2_TILT_X',
  //   timestamp: '2025-12-03T20:00:00Z'
  // }
});
```

#### alert_acknowledged
Emitido cuando se reconoce una alerta.

```javascript
socket.on('alert_acknowledged', (data) => {
  console.log('Alerta reconocida:', data.alert_id);
});
```

## Configuración Avanzada

En `alert_engine.py`:

```python
# Timeout para considerar dispositivo offline (segundos)
DEVICE_TIMEOUT = 30  # Default: 30s

# Ventana de debouncing (segundos)
DEBOUNCE_WINDOW = 60  # Default: 60s entre alertas del mismo tipo

# Límite anti-flood
MAX_ALERTS_PER_HOUR = 20  # Default: 20 alertas/hora por sensor
```

## Base de Datos

### Tabla: alerts

```sql
CREATE TABLE alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,          -- ISO8601 UTC
    sensor_id TEXT,                   -- Sensor afectado (NULL si es sistema)
    rig_id TEXT,                      -- RIG afectado
    level TEXT NOT NULL,              -- INFO, WARN, ALARM, CRITICAL
    code TEXT NOT NULL,               -- Código de alerta
    message TEXT NOT NULL,            -- Descripción legible
    ack INTEGER NOT NULL DEFAULT 0,   -- 0=activa, 1=reconocida
    
    FOREIGN KEY (sensor_id) REFERENCES sensors(sensor_id)
);
```

### Índices

```sql
CREATE INDEX idx_alerts_ack ON alerts(ack);
CREATE INDEX idx_alerts_timestamp ON alerts(timestamp);
```

## Debouncing

El sistema implementa **debouncing** para evitar spam de alertas:

1. Cuando se genera una alerta de tipo `(sensor_id, code)`, se registra el timestamp
2. Si se intenta generar la misma alerta antes de `DEBOUNCE_WINDOW` (60s), se **descarta**
3. Pasados 60s, se permite una nueva alerta del mismo tipo

**Ejemplo:**
```
20:00:00 - THRESHOLD_EXCEEDED_HI para UNIT_2_TILT_X → ✅ Alerta creada
20:00:15 - THRESHOLD_EXCEEDED_HI para UNIT_2_TILT_X → ❌ Descartada (debounce)
20:00:45 - THRESHOLD_EXCEEDED_HI para UNIT_2_TILT_X → ❌ Descartada (debounce)
20:01:05 - THRESHOLD_EXCEEDED_HI para UNIT_2_TILT_X → ✅ Alerta creada (pasaron 65s)
```

## Estado de Dispositivos

El campo `last_seen` en la tabla `devices` se actualiza automáticamente:

- **Actualización**: Cada vez que PollingService lee telemetría exitosa
- **Monitoreo**: AlertEngine verifica cada 10s si `last_seen > 30s`
- **Alerta**: Si timeout excedido → `DEVICE_OFFLINE` (nivel WARN)

## Casos de Uso

### 1. Supervisión 24/7 sin pérdida de alertas
Aunque no estés viendo el dashboard, las alertas se almacenan en BD.

### 2. Análisis histórico
Consulta alertas pasadas para detectar patrones:
```bash
curl 'http://localhost:8080/api/alerts?limit=1000' > alertas_historicas.json
```

### 3. Integración con sistemas externos
- ThingsBoard: Publicar alertas como telemetría
- Email/SMS: Trigger basado en nivel CRITICAL
- PLC: Enviar comando de parada si CRITICAL

### 4. Dashboard en tiempo real
Escuchar evento `new_alert` vía WebSocket para actualizar UI automáticamente.

## Testing

### Generar alerta de umbral
Modifica temporalmente un umbral para forzar alerta:

```python
# En database
db.upsert_sensor({
    'sensor_id': 'UNIT_2_TILT_X',
    'alarm_hi': 0.5  # Umbral muy bajo → forzará alerta
})
```

### Generar alerta de dispositivo offline
Detener el firmware de un dispositivo y esperar 30s.

### Verificar debouncing
Consultar logs para ver mensajes:
```
Alerta THRESHOLD_EXCEEDED_HI para UNIT_2_TILT_X en debounce, ignorando
```

## Próximas Mejoras

- [ ] Panel de alertas en dashboard.html
- [ ] Notificaciones toast en frontend
- [ ] Vista dedicada /alerts con filtros
- [ ] Exportación de alertas (CSV/JSON)
- [ ] Integración con ThingsBoard
- [ ] Envío de emails para CRITICAL
- [ ] Histograma de alertas por hora/día
- [ ] Auto-reconocimiento tras N horas

## Autor

Sergio Lobo Alonso - TFM UNIR  
Diciembre 2025

## Auto-Resolución de Alertas

### Descripción

El sistema implementa **auto-resolución automática** de alertas cuando las condiciones que las generaron vuelven a la normalidad.

### Funcionamiento

#### Alertas de Umbral (THRESHOLD_EXCEEDED)

Cuando un sensor viola un umbral (alarm_lo o alarm_hi):
1. ✅ Se **genera** la alerta y se marca como activa
2. �� Se **registra** en cache de alertas activas
3. ⏳ En cada nueva medida del sensor, se verifica:
   - Si el valor sigue fuera de rango → No hace nada
   - Si el valor vuelve a rango normal → **Auto-reconoce** la alerta

**Ejemplo:**
```
20:00:00 - UNIT_2_TILT_X = -27.5° → ❌ Viola umbral (-10°)
         → Genera alerta ID 123 (THRESHOLD_EXCEEDED_LO)
         
20:00:15 - UNIT_2_TILT_X = -25.0° → ❌ Sigue violando
         → No genera nueva alerta (debouncing activo)
         
20:01:00 - UNIT_2_TILT_X = -8.5° → ✅ Vuelve a rango normal
         → Auto-reconoce alerta ID 123
         → Mensaje: "Valor normalizado: -8.50 deg"
```

#### Alertas de Dispositivo Offline (DEVICE_OFFLINE)

Cuando un dispositivo no envía telemetría > 30s:
1. ✅ Se **genera** alerta de tipo WARN
2. 📌 Se **registra** en cache de alertas activas
3. ⏳ Cada 10s se verifica el estado:
   - Si sigue offline → No hace nada
   - Si vuelve online (recibe telemetría) → **Auto-reconoce** la alerta

**Ejemplo:**
```
20:00:00 - Dispositivo PA_L última telemetría
20:00:35 - Pasan 35s sin telemetría → ❌ Timeout excedido (30s)
         → Genera alerta ID 456 (DEVICE_OFFLINE)
         
20:01:00 - Sigue sin telemetría
         → Alerta sigue activa
         
20:01:15 - Llega telemetría de PA_L → ✅ Vuelve online
         → Auto-reconoce alerta ID 456
         → Mensaje: "Dispositivo PA_L (Unit 2) vuelve online"
```

### Ventajas

1. **Reduce ruido**: Solo se muestran alertas de condiciones **actualmente problemáticas**
2. **Refleja estado real**: El panel de alertas siempre muestra la situación **actual**
3. **No requiere intervención manual**: Las alertas se resuelven solas cuando todo vuelve a la normalidad
4. **Historial completo**: Las alertas reconocidas se mantienen en BD para análisis histórico

### Notificaciones WebSocket

Cuando una alerta se auto-resuelve:
```javascript
socket.on('alert_acknowledged', (data) => {
  // data = {
  //   alert_id: 123,
  //   auto: true,  // Indica que fue auto-resuelta
  //   reason: "Valor normalizado: -8.50 deg"
  // }
});
```

### Logs

El sistema registra cada auto-resolución:
```
✅ Auto-resolución: Alerta 123 (THRESHOLD_EXCEEDED_LO) para UNIT_2_TILT_X reconocida - Valor normalizado: -8.50 deg
✅ Auto-resolución: Alerta 456 (DEVICE_OFFLINE) para sistema reconocida - Dispositivo PA_L (Unit 2) vuelve online
```

### Configuración

La auto-resolución está **siempre activa** y no requiere configuración adicional.

Para **deshabilitar** la auto-resolución (no recomendado), modificar `alert_engine.py`:
```python
# En check_measurement_thresholds():
# Comentar sección de AUTO-RESOLUCIÓN
```

### Consulta de Alertas Resueltas

Las alertas auto-resueltas se pueden consultar:
```bash
# Ver todas las alertas (activas y reconocidas)
curl 'http://localhost:8080/api/alerts?limit=100'

# Ver solo alertas reconocidas
curl 'http://localhost:8080/api/alerts?ack=true&limit=50'
```

---

**Última actualización:** 3 Diciembre 2025
