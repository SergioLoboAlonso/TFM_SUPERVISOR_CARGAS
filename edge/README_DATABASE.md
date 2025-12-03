# 📊 Módulo de Base de Datos SQLite - Edge Layer

## Descripción General

Módulo de persistencia para el sistema IIoT Edge basado en Raspberry Pi. Utiliza **SQLite** como base de datos embebida para almacenar telemetría, configuración de sensores y alertas locales.

## Arquitectura

```
┌─────────────────────────────────────────────────────────────┐
│                    RASPBERRY PI (Edge)                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐      ┌─────────────────────┐            │
│  │  ModbusMaster├──────►  PollingService     │            │
│  └──────────────┘      └──────────┬──────────┘            │
│         │                         │                        │
│         │  RS-485/Modbus RTU      │                        │
│         ▼                         ▼                        │
│  ┌──────────────────────────────────────────┐             │
│  │      SQLite (measurements.db)            │             │
│  ├──────────────────────────────────────────┤             │
│  │  sensors      │  measurements  │  alerts │             │
│  │  (config)     │  (telemetry)   │  (local)│             │
│  └──────────────────────────────────────────┘             │
│         │                │                 │               │
│         ▼                ▼                 ▼               │
│  ┌────────────┐  ┌────────────┐  ┌──────────────┐        │
│  │   Motor    │  │   Bridge   │  │   Dashboard  │        │
│  │  Alertas   │  │ ThingsBoard│  │    Local     │        │
│  └────────────┘  └────────────┘  └──────────────┘        │
│                         │                                  │
└─────────────────────────┼──────────────────────────────────┘
                          │
                          ▼
                  ┌───────────────┐
                  │  ThingsBoard  │
                  │   (Cloud)     │
                  └───────────────┘
```

## Esquema de Base de Datos

### Tabla: `sensors`

Almacena la configuración de cada sensor físico conectado al bus Modbus.

```sql
CREATE TABLE sensors (
    sensor_id TEXT PRIMARY KEY,          -- ID lógico: "TILT_01", "WIND_01"
    type TEXT NOT NULL,                  -- Tipo: "tilt", "wind", "load"
    rig_id TEXT NOT NULL,                -- Estructura: "RIG_01", "TOWER_A"
    modbus_address INTEGER NOT NULL,     -- Unit ID Modbus (1..247)
    register INTEGER NOT NULL,           -- Registro Modbus principal
    unit TEXT NOT NULL,                  -- Unidad: "deg", "m_s", "kg", "g"
    alarm_lo REAL,                       -- Umbral inferior (opcional)
    alarm_hi REAL,                       -- Umbral superior (opcional)
    created_at TEXT NOT NULL,            -- Timestamp ISO8601 de alta
    enabled INTEGER NOT NULL DEFAULT 1   -- 1=activo, 0=deshabilitado
)
```

**Ejemplo de datos:**
| sensor_id | type  | rig_id | modbus_address | register | unit | alarm_lo | alarm_hi |
|-----------|-------|--------|----------------|----------|------|----------|----------|
| TILT_01   | tilt  | RIG_01 | 1              | 0        | deg  | -5.0     | 5.0      |
| WIND_01   | wind  | RIG_01 | 2              | 13       | m_s  | NULL     | 25.0     |
| LOAD_A1   | load  | RIG_02 | 3              | 12       | kg   | 0.0      | 500.0    |

### Tabla: `measurements`

Serie temporal de telemetría. Cada fila representa una lectura de un sensor.

```sql
CREATE TABLE measurements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,                 -- ISO8601 UTC
    sensor_id TEXT NOT NULL,                 -- Ref a sensors.sensor_id
    type TEXT NOT NULL,                      -- "tilt", "wind", "load"
    value REAL NOT NULL,                     -- Valor numérico
    unit TEXT NOT NULL,                      -- Unidad física
    quality TEXT NOT NULL DEFAULT 'OK',      -- OK, WARN, ALARM, ERROR_COMMS
    sent_to_cloud INTEGER NOT NULL DEFAULT 0 -- 0=pendiente, 1=enviado
)

-- Índices para rendimiento
CREATE INDEX idx_measurements_timestamp ON measurements(timestamp);
CREATE INDEX idx_measurements_sensor_id ON measurements(sensor_id);
CREATE INDEX idx_measurements_sent ON measurements(sent_to_cloud);
```

**Ejemplo de datos:**
| id | timestamp            | sensor_id | type | value | unit | quality | sent_to_cloud |
|----|---------------------|-----------|------|-------|------|---------|---------------|
| 1  | 2025-12-03T18:00:00Z| TILT_01   | tilt | 2.35  | deg  | OK      | 0             |
| 2  | 2025-12-03T18:00:00Z| WIND_01   | wind | 12.5  | m_s  | OK      | 0             |
| 3  | 2025-12-03T18:00:01Z| TILT_01   | tilt | 5.8   | deg  | ALARM   | 0             |

### Tabla: `alerts`

Alertas generadas localmente en el Edge cuando se detectan anomalías.

```sql
CREATE TABLE alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,              -- ISO8601 UTC
    sensor_id TEXT,                       -- Sensor afectado (opcional)
    rig_id TEXT,                          -- Rig afectado (opcional)
    level TEXT NOT NULL,                  -- INFO, WARN, ALARM, CRITICAL
    code TEXT NOT NULL,                   -- Código: "TILT_LIMIT_EXCEEDED"
    message TEXT NOT NULL,                -- Descripción legible
    ack INTEGER NOT NULL DEFAULT 0        -- 0=no reconocida, 1=reconocida
)

-- Índices
CREATE INDEX idx_alerts_ack ON alerts(ack);
CREATE INDEX idx_alerts_timestamp ON alerts(timestamp);
```

**Ejemplo de datos:**
| id | timestamp            | sensor_id | rig_id | level    | code                | message                              | ack |
|----|---------------------|-----------|--------|----------|---------------------|--------------------------------------|-----|
| 1  | 2025-12-03T18:00:01Z| TILT_01   | RIG_01 | ALARM    | TILT_LIMIT_EXCEEDED | Inclinación de 5.8° supera umbral   | 0   |
| 2  | 2025-12-03T18:05:00Z| WIND_01   | RIG_01 | CRITICAL | WIND_CRITICAL       | Viento de 27.3 m/s supera 25.0 m/s  | 0   |

## Instalación y Configuración

### 1. Ruta de la Base de Datos

Por defecto, la BD se crea en:
```
/opt/edge/db/measurements.db
```

Para cambiar la ruta, editar en `src/database.py`:
```python
DB_PATH = "/custom/path/measurements.db"
```

### 2. Inicialización

```bash
cd /home/edge_sergio/Desktop/TFM_SUPERVISOR_CARGAS/edge

# Opción 1: Inicializar usando script standalone
python3 src/database.py

# Opción 2: Inicializar con ruta custom
python3 src/database.py /tmp/custom_measurements.db

# Opción 3: Desde código Python
python3 -c "from src.database import init_db; init_db()"
```

### 3. Verificar Creación

```bash
# Listar archivos
ls -lh /opt/edge/db/

# Inspeccionar con sqlite3
sqlite3 /opt/edge/db/measurements.db
sqlite> .tables
alerts       measurements sensors
sqlite> .schema sensors
sqlite> SELECT COUNT(*) FROM measurements;
sqlite> .quit
```

## Uso desde Código Python

### Importar el Módulo

```python
from src.database import Database

# Inicializar (usa DB_PATH por defecto)
db = Database()

# O usar ruta custom
db = Database('/tmp/test_measurements.db')
```

### Operaciones con Sensores

```python
# Registrar un sensor
db.upsert_sensor({
    'sensor_id': 'TILT_01',
    'type': 'tilt',
    'rig_id': 'RIG_01',
    'modbus_address': 1,
    'register': 0,
    'unit': 'deg',
    'alarm_lo': -5.0,
    'alarm_hi': 5.0,
    'enabled': 1
})

# Obtener un sensor
sensor = db.get_sensor('TILT_01')
print(sensor['type'])  # 'tilt'

# Listar todos los sensores activos
sensors = db.get_all_sensors(enabled_only=True)
for s in sensors:
    print(f"{s['sensor_id']}: {s['type']} en {s['rig_id']}")
```

### Operaciones con Telemetría

```python
from datetime import datetime, timedelta

# Insertar una medida
db.insert_measurement({
    'sensor_id': 'TILT_01',
    'type': 'tilt',
    'value': 2.35,
    'unit': 'deg',
    'quality': 'OK'
})

# Consultar últimas N medidas
latest = db.get_measurements(sensor_id='TILT_01', limit=10)
for m in latest:
    print(f"{m['timestamp']}: {m['value']} {m['unit']}")

# Consultar rango de tiempo
since = datetime.utcnow() - timedelta(hours=24)
data = db.get_measurements(sensor_id='TILT_01', since=since, limit=1000)

# Obtener medidas pendientes de enviar a ThingsBoard
unsent = db.get_unsent_measurements(limit=100)
print(f"Pendientes: {len(unsent)}")

# Marcar como enviadas
ids = [m['id'] for m in unsent]
db.mark_as_sent(ids)
```

### Operaciones con Alertas

```python
# Generar una alerta
db.insert_alert({
    'level': 'ALARM',
    'code': 'TILT_LIMIT_EXCEEDED',
    'message': 'Inclinación de 5.8° supera umbral de 5.0°',
    'sensor_id': 'TILT_01',
    'rig_id': 'RIG_01'
})

# Consultar alertas no reconocidas
alerts = db.get_alerts(ack=False, limit=10)
for a in alerts:
    print(f"[{a['level']}] {a['code']}: {a['message']}")

# Reconocer una alerta
db.acknowledge_alert(alert_id=1)

# Filtrar por nivel
critical = db.get_alerts(level='CRITICAL', limit=50)
```

### Mantenimiento

```python
# Estadísticas de la BD
stats = db.get_db_stats()
print(f"Tamaño: {stats['db_size_mb']} MB")
print(f"Sensores: {stats['sensor_count']}")
print(f"Medidas: {stats['measurement_count']}")
print(f"Alertas: {stats['alert_count']}")

# Limpieza de datos antiguos (>30 días)
deleted = db.cleanup_old_data(days=30)
print(f"Eliminados {deleted} registros")
```

## Integración con Componentes Existentes

### 1. PollingService → Base de Datos

Modificar `src/polling_service.py` para guardar telemetría:

```python
from database import Database

class PollingService:
    def __init__(self, ...):
        # ...
        self.db = Database()
    
    def _read_telemetry(self, unit_id):
        # ... lectura Modbus ...
        normalized = self.normalizer.normalize_telemetry(raw_regs, capabilities)
        
        # Guardar en BD
        device = self.device_manager.get_device(unit_id)
        sensor_id = f"{device.alias}_{unit_id}"  # Ej: "WindMeter_1"
        
        # Guardar ángulo X
        if 'angle_x_deg' in normalized:
            self.db.insert_measurement({
                'sensor_id': sensor_id,
                'type': 'tilt',
                'value': normalized['angle_x_deg'],
                'unit': 'deg',
                'quality': 'OK'
            })
        
        # Guardar velocidad de viento
        if 'wind_speed_mps' in normalized:
            self.db.insert_measurement({
                'sensor_id': sensor_id,
                'type': 'wind',
                'value': normalized['wind_speed_mps'],
                'unit': 'm_s',
                'quality': 'OK'
            })
```

### 2. Motor de Alertas

Crear nuevo módulo `src/alert_engine.py`:

```python
from database import Database
from datetime import datetime, timedelta

class AlertEngine:
    def __init__(self, db_path=None):
        self.db = Database(db_path)
    
    def check_alerts(self):
        """Revisa últimas medidas y genera alertas si superan umbrales"""
        sensors = self.db.get_all_sensors()
        
        for sensor in sensors:
            # Obtener última medida
            latest = self.db.get_measurements(
                sensor_id=sensor['sensor_id'], 
                limit=1
            )
            
            if not latest:
                continue
            
            measurement = latest[0]
            value = measurement['value']
            
            # Verificar umbrales
            if sensor['alarm_hi'] and value > sensor['alarm_hi']:
                self.db.insert_alert({
                    'level': 'ALARM',
                    'code': f"{sensor['type'].upper()}_HIGH",
                    'message': f"{sensor['sensor_id']}: {value:.2f} {sensor['unit']} > {sensor['alarm_hi']}",
                    'sensor_id': sensor['sensor_id'],
                    'rig_id': sensor['rig_id']
                })
            
            elif sensor['alarm_lo'] and value < sensor['alarm_lo']:
                self.db.insert_alert({
                    'level': 'ALARM',
                    'code': f"{sensor['type'].upper()}_LOW",
                    'message': f"{sensor['sensor_id']}: {value:.2f} {sensor['unit']} < {sensor['alarm_lo']}",
                    'sensor_id': sensor['sensor_id'],
                    'rig_id': sensor['rig_id']
                })

# Uso
engine = AlertEngine()
engine.check_alerts()  # Ejecutar cada ciclo de polling
```

### 3. Bridge ThingsBoard

Crear `src/thingsboard_bridge.py`:

```python
from database import Database
import requests
from datetime import datetime

class ThingsBoardBridge:
    def __init__(self, tb_url, tb_token, db_path=None):
        self.tb_url = tb_url
        self.tb_token = tb_token
        self.db = Database(db_path)
    
    def sync_telemetry(self):
        """Lee medidas no enviadas y las publica a ThingsBoard"""
        unsent = self.db.get_unsent_measurements(limit=100)
        
        if not unsent:
            return
        
        # Agrupar por sensor para publicar agregados
        by_sensor = {}
        for m in unsent:
            sensor_id = m['sensor_id']
            if sensor_id not in by_sensor:
                by_sensor[sensor_id] = []
            by_sensor[sensor_id].append(m)
        
        # Publicar telemetría agregada a ThingsBoard
        for sensor_id, measurements in by_sensor.items():
            values = [m['value'] for m in measurements]
            
            telemetry = {
                'last_value': values[0],
                'min_value': min(values),
                'max_value': max(values),
                'avg_value': sum(values) / len(values),
                'sample_count': len(values),
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # POST a ThingsBoard HTTP API
            response = requests.post(
                f"{self.tb_url}/api/v1/{self.tb_token}/telemetry",
                json=telemetry
            )
            
            if response.status_code == 200:
                # Marcar como enviadas
                ids = [m['id'] for m in measurements]
                self.db.mark_as_sent(ids)

# Uso
bridge = ThingsBoardBridge(
    tb_url='https://demo.thingsboard.io',
    tb_token='YOUR_DEVICE_TOKEN'
)
bridge.sync_telemetry()  # Ejecutar periódicamente
```

## Scripts de Utilidad

### Script de Ejemplo Completo

```bash
python3 examples/database_usage.py
```

Este script demuestra:
- ✅ Inicialización de BD
- ✅ Registro de sensores
- ✅ Inserción de telemetría
- ✅ Consultas de datos históricos
- ✅ Generación de alertas
- ✅ Sincronización con ThingsBoard

### Inspección Manual

```bash
# Listar sensores
sqlite3 /opt/edge/db/measurements.db "SELECT * FROM sensors;"

# Contar medidas
sqlite3 /opt/edge/db/measurements.db "SELECT COUNT(*) FROM measurements;"

# Últimas 10 medidas
sqlite3 /opt/edge/db/measurements.db \
  "SELECT timestamp, sensor_id, value, unit FROM measurements ORDER BY timestamp DESC LIMIT 10;"

# Alertas activas
sqlite3 /opt/edge/db/measurements.db \
  "SELECT * FROM alerts WHERE ack = 0 ORDER BY timestamp DESC;"
```

## Mantenimiento Automático

### Limpieza Programada

Agregar a `src/app.py` al iniciar el servidor:

```python
from database import Database
from config import Config

# Al iniciar
db = Database()
deleted = db.cleanup_old_data(days=30)
logger.info(f"🗑️ Limpieza inicial: {deleted} registros antiguos eliminados")
```

### Cron Job (opcional)

```bash
# Editar crontab
crontab -e

# Limpiar BD cada domingo a las 3:00 AM
0 3 * * 0 /home/edge_sergio/Desktop/TFM_SUPERVISOR_CARGAS/edge/venv/bin/python3 -c \
  "from src.database import Database; db = Database(); db.cleanup_old_data(30)"
```

## Backup y Recuperación

### Backup Manual

```bash
# Copiar archivo SQLite
cp /opt/edge/db/measurements.db \
   /opt/edge/db/backups/measurements_$(date +%Y%m%d_%H%M%S).db

# O usar comando sqlite3 .backup
sqlite3 /opt/edge/db/measurements.db \
  ".backup /opt/edge/db/backups/measurements_backup.db"
```

### Restauración

```bash
# Detener servicio edge
sudo systemctl stop tfm-edge.service

# Restaurar backup
cp /opt/edge/db/backups/measurements_20251203.db \
   /opt/edge/db/measurements.db

# Reiniciar servicio
sudo systemctl start tfm-edge.service
```

## Troubleshooting

### Error: "database is locked"

**Causa:** Otra conexión tiene la BD bloqueada.

**Solución:**
```python
# Usar timeout en conexiones
conn = sqlite3.connect(db_path, timeout=10.0)
```

### BD crece demasiado

**Solución:** Ejecutar limpieza + VACUUM:
```bash
sqlite3 /opt/edge/db/measurements.db << EOF
DELETE FROM measurements WHERE timestamp < datetime('now', '-30 days');
VACUUM;
EOF
```

### Verificar integridad

```bash
sqlite3 /opt/edge/db/measurements.db "PRAGMA integrity_check;"
# Salida esperada: ok
```

## Referencias

- [SQLite Documentation](https://www.sqlite.org/docs.html)
- [Python sqlite3 Module](https://docs.python.org/3/library/sqlite3.html)
- [ThingsBoard HTTP API](https://thingsboard.io/docs/reference/http-api/)

---

**Versión:** 1.0  
**Fecha:** 3 de diciembre de 2025  
**Autor:** Edge Layer - TFM Supervisor de Cargas
