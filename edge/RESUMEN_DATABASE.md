# 🎯 RESUMEN EJECUTIVO - Módulo de Base de Datos SQLite

## ✅ Entregables Completados

### 1. Código de Inicialización (`src/database.py`)

**Módulo completo** con:
- ✅ Función `init_db()` idempotente para crear esquema
- ✅ Clase `Database` con API completa de acceso a datos
- ✅ 3 tablas: `sensors`, `measurements`, `alerts`
- ✅ Índices optimizados para consultas frecuentes
- ✅ Manejo de transacciones y context managers
- ✅ Limpieza automática de datos antiguos

**Ruta por defecto:** `/opt/edge/db/measurements.db` (configurable)

### 2. Esquema de Base de Datos

#### Tabla `sensors` - Configuración de Sensores
```sql
CREATE TABLE sensors (
    sensor_id TEXT PRIMARY KEY,
    type TEXT NOT NULL,              -- "tilt", "wind", "load"
    rig_id TEXT NOT NULL,            -- "RIG_01", "TOWER_A"
    modbus_address INTEGER NOT NULL, -- Unit ID Modbus
    register INTEGER NOT NULL,       -- Registro principal
    unit TEXT NOT NULL,              -- "deg", "m_s", "kg", "g"
    alarm_lo REAL,                   -- Umbral inferior
    alarm_hi REAL,                   -- Umbral superior
    created_at TEXT NOT NULL,        -- ISO8601
    enabled INTEGER NOT NULL
)
```

#### Tabla `measurements` - Telemetría
```sql
CREATE TABLE measurements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,         -- ISO8601 UTC
    sensor_id TEXT NOT NULL,
    type TEXT NOT NULL,
    value REAL NOT NULL,
    unit TEXT NOT NULL,
    quality TEXT NOT NULL,           -- OK, WARN, ALARM, ERROR_COMMS
    sent_to_cloud INTEGER NOT NULL   -- 0=pendiente, 1=enviado
)
-- Índices: timestamp, sensor_id, sent_to_cloud
```

#### Tabla `alerts` - Alertas Locales
```sql
CREATE TABLE alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    sensor_id TEXT,
    rig_id TEXT,
    level TEXT NOT NULL,             -- INFO, WARN, ALARM, CRITICAL
    code TEXT NOT NULL,
    message TEXT NOT NULL,
    ack INTEGER NOT NULL             -- 0=no reconocida, 1=reconocida
)
-- Índices: ack, timestamp
```

### 3. Documentación

- ✅ **README_DATABASE.md**: Guía completa (arquitectura, uso, integración)
- ✅ **examples/database_usage.py**: Ejemplo ejecutable completo
- ✅ **tests/test_database.py**: Suite de tests unitarios (6 tests, todos pasando)

### 4. Tests y Validación

```bash
$ python3 tests/test_database.py

📊 RESULTADOS: 6 passed, 0 failed
✅ TODOS LOS TESTS PASARON
```

**Tests incluidos:**
- ✅ Inicialización de BD
- ✅ CRUD de sensores
- ✅ CRUD de medidas (insert, query, mark_as_sent)
- ✅ CRUD de alertas
- ✅ Estadísticas y limpieza
- ✅ Foreign key constraints

## 📊 Arquitectura Implementada

```
┌─────────────────────────────────────────────────────────────┐
│                    RASPBERRY PI (Edge)                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  PollingService ──┬──> SQLite (measurements.db)            │
│                   │        ├─ sensors                       │
│                   │        ├─ measurements                  │
│                   │        └─ alerts                        │
│                   │                                         │
│                   ├──> Motor de Alertas (lee de BD)        │
│                   │                                         │
│                   └──> Bridge ThingsBoard (lee de BD)      │
│                            └──> ThingsBoard Cloud           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 Cómo Usar

### Inicialización Standalone

```bash
# Opción 1: Usar ruta por defecto (/opt/edge/db/measurements.db)
python3 src/database.py

# Opción 2: Ruta custom
python3 src/database.py /tmp/test_measurements.db
```

### Uso en Código

```python
from src.database import Database

# Inicializar
db = Database()

# Registrar sensor
db.upsert_sensor({
    'sensor_id': 'TILT_01',
    'type': 'tilt',
    'rig_id': 'RIG_01',
    'modbus_address': 1,
    'register': 0,
    'unit': 'deg',
    'alarm_lo': -5.0,
    'alarm_hi': 5.0
})

# Guardar telemetría
db.insert_measurement({
    'sensor_id': 'TILT_01',
    'type': 'tilt',
    'value': 2.35,
    'unit': 'deg',
    'quality': 'OK'
})

# Consultar últimas lecturas
latest = db.get_measurements(sensor_id='TILT_01', limit=10)

# Generar alerta
db.insert_alert({
    'level': 'ALARM',
    'code': 'TILT_LIMIT_EXCEEDED',
    'message': 'Inclinación supera umbral',
    'sensor_id': 'TILT_01'
})

# Sincronización ThingsBoard
unsent = db.get_unsent_measurements()
# ... publicar a ThingsBoard ...
db.mark_as_sent([m['id'] for m in unsent])

# Limpieza (>30 días)
db.cleanup_old_data(days=30)
```

### Ejemplo Completo

```bash
python3 examples/database_usage.py
```

**Salida:**
```
✅ BD inicializada: /tmp/test_measurements.db
✅ Sensor TILT_01 registrado (inclinómetro, umbrales ±5°)
✅ Sensor WIND_01 registrado (anemómetro, umbral 25 m/s)
✅ Insertadas 30 medidas (10 por sensor)
📤 Medidas pendientes de enviar a ThingsBoard: 30
✅ 30 medidas marcadas como enviadas
📊 Estadísticas de BD:
   Tamaño: 0.04 MB
   Sensores: 3
   Medidas: 30
   Alertas: 0
```

## 🔧 Integración con Sistema Existente

### 1. PollingService → Base de Datos

```python
# En src/polling_service.py
from database import Database

class PollingService:
    def __init__(self, ...):
        self.db = Database()
    
    def _read_telemetry(self, unit_id):
        # ... lectura Modbus ...
        
        # Guardar en BD
        if 'angle_x_deg' in normalized:
            self.db.insert_measurement({
                'sensor_id': f"TILT_{unit_id}",
                'type': 'tilt',
                'value': normalized['angle_x_deg'],
                'unit': 'deg',
                'quality': 'OK'
            })
```

### 2. Motor de Alertas

```python
# Crear src/alert_engine.py
from database import Database

class AlertEngine:
    def check_alerts(self):
        sensors = self.db.get_all_sensors()
        for sensor in sensors:
            latest = self.db.get_measurements(sensor_id=sensor['sensor_id'], limit=1)[0]
            if latest['value'] > sensor['alarm_hi']:
                self.db.insert_alert({
                    'level': 'ALARM',
                    'code': f"{sensor['type'].upper()}_HIGH",
                    'message': f"Valor {latest['value']} supera umbral {sensor['alarm_hi']}"
                })
```

### 3. Bridge ThingsBoard

```python
# Crear src/thingsboard_bridge.py
class ThingsBoardBridge:
    def sync_telemetry(self):
        unsent = self.db.get_unsent_measurements(limit=100)
        # Publicar a ThingsBoard via HTTP API o MQTT
        # ...
        self.db.mark_as_sent([m['id'] for m in unsent])
```

## 📁 Archivos Creados

```
edge/
├── src/
│   └── database.py              # ⭐ Módulo principal (587 líneas)
├── examples/
│   └── database_usage.py        # Ejemplo completo (310 líneas)
├── tests/
│   └── test_database.py         # Suite de tests (312 líneas)
└── README_DATABASE.md           # Documentación completa (600+ líneas)
```

**Total:** ~1800 líneas de código y documentación

## ✨ Características Destacables

1. **Idempotente:** `init_db()` puede ejecutarse múltiples veces sin borrar datos
2. **Portable:** Archivo SQLite único, sin dependencias externas
3. **Eficiente:** Índices optimizados para consultas frecuentes
4. **Robusto:** Context managers para manejo seguro de conexiones
5. **Completo:** API CRUD completa para sensores, medidas y alertas
6. **Probado:** Suite de tests con 100% de éxito
7. **Documentado:** Ejemplos ejecutables y guía completa

## 🎓 Para Defensa del TFM

**Puntos clave:**

1. **Arquitectura Edge → Cloud:**
   - Edge guarda TODO en BD local (resiliencia)
   - Bridge sincroniza con ThingsBoard cuando haya conectividad
   - Motor de alertas local (autonomía)

2. **Persistencia ligera:**
   - SQLite ideal para Raspberry Pi
   - Sin servidor externo (embebida)
   - ACID compliant (transacciones seguras)

3. **Series temporales:**
   - Telemetría con timestamp ISO8601
   - Índices por tiempo y sensor
   - Limpieza automática (retención configurable)

4. **Calidad de datos:**
   - Campo `quality` (OK, WARN, ALARM, ERROR_COMMS)
   - Flag `sent_to_cloud` para sincronización
   - Umbrales configurables por sensor

5. **Trazabilidad:**
   - Todas las alertas registradas
   - Auditoría completa
   - Reconocimiento de alertas (ack)

## 📝 Próximos Pasos (Recomendados)

1. **Integrar con PollingService:**
   - Modificar `src/polling_service.py` para guardar telemetría
   - Mapear capabilities → tipo de sensor

2. **Crear Motor de Alertas:**
   - Implementar `src/alert_engine.py`
   - Ejecutar checks cada ciclo de polling
   - Notificaciones locales (email, Telegram, etc.)

3. **Desarrollar Bridge ThingsBoard:**
   - Implementar `src/thingsboard_bridge.py`
   - HTTP API o MQTT
   - Sincronización periódica (cron o thread)

4. **API REST endpoints:**
   - `GET /api/history/<sensor_id>?hours=24`
   - `GET /api/alerts?ack=false`
   - `POST /api/alerts/<id>/acknowledge`
   - `GET /api/database/stats`

---

**Estado:** ✅ **COMPLETADO Y PROBADO**  
**Fecha:** 3 de diciembre de 2025  
**Versión:** 1.0
