# 🎉 MÓDULO DE BASE DE DATOS SQLite - COMPLETADO

## ✅ Verificación Exitosa

El módulo ha sido creado, probado y verificado completamente:

```
✅ Archivos creados: 6
✅ Líneas de código: ~2277
✅ Tests pasados: 6/6
✅ Ejemplo ejecutado: OK
✅ Imports verificados: OK
```

## 📦 Archivos Entregados

### 1. Código Principal
- **`src/database.py`** (700 líneas)
  - Función `init_db()` para inicialización
  - Clase `Database` con API completa
  - 3 tablas: sensors, measurements, alerts
  - Índices optimizados
  - Manejo de transacciones

### 2. Ejemplos y Tests
- **`examples/database_usage.py`** (333 líneas)
  - Ejemplo ejecutable completo
  - Demostración de todas las funcionalidades
  
- **`tests/test_database.py`** (350 líneas)
  - 6 tests unitarios (100% éxito)
  - Cubre CRUD completo de todas las tablas

### 3. Documentación
- **`README_DATABASE.md`** (567 líneas)
  - Guía completa de uso
  - Ejemplos de código
  - Integración con componentes
  
- **`RESUMEN_DATABASE.md`** (327 líneas)
  - Resumen ejecutivo
  - Arquitectura implementada
  - Próximos pasos
  
- **`ARQUITECTURA_DATABASE_VISUAL.txt`**
  - Diagramas visuales ASCII
  - Flujo de datos
  - Ejemplos de tablas

### 4. Scripts de Verificación
- **`VERIFICACION_DATABASE.sh`**
  - Script automatizado de verificación
  - Ejecuta tests y valida imports

## 🚀 Uso Rápido

### Inicialización

```bash
# Opción 1: Desde línea de comandos
python3 src/database.py

# Opción 2: Desde código Python
python3 -c "from src.database import init_db; init_db()"
```

### Ejemplo Completo

```bash
python3 examples/database_usage.py
```

### Tests Unitarios

```bash
python3 tests/test_database.py
```

### Código Básico

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
for m in latest:
    print(f"{m['timestamp']}: {m['value']} {m['unit']}")
```

## 📊 Esquema de Base de Datos

### Tabla `sensors`
```sql
sensor_id (TEXT PK) | type | rig_id | modbus_address | register | 
unit | alarm_lo | alarm_hi | created_at | enabled
```

### Tabla `measurements`
```sql
id (INT PK) | timestamp | sensor_id (FK) | type | value | 
unit | quality | sent_to_cloud
```

### Tabla `alerts`
```sql
id (INT PK) | timestamp | sensor_id | rig_id | level | 
code | message | ack
```

## 🔧 Instalación Opcional de sqlite3-tools

El módulo `database.py` **NO requiere** `sqlite3-tools` para funcionar (usa el módulo `sqlite3` de Python que viene por defecto).

Sin embargo, si quieres inspeccionar la BD manualmente desde terminal:

```bash
# Debian/Ubuntu/Raspberry Pi OS
sudo apt-get update
sudo apt-get install -y sqlite3

# Verificar instalación
sqlite3 --version
```

### Uso de sqlite3 CLI

```bash
# Abrir BD
sqlite3 /opt/edge/db/measurements.db

# Listar tablas
.tables

# Ver esquema
.schema sensors

# Consultas SQL
SELECT * FROM sensors;
SELECT COUNT(*) FROM measurements;
SELECT * FROM alerts WHERE ack = 0;

# Salir
.quit
```

## 📚 Documentación Completa

Para información detallada, consulta:

1. **README_DATABASE.md** - Guía completa de uso
2. **RESUMEN_DATABASE.md** - Resumen ejecutivo
3. **ARQUITECTURA_DATABASE_VISUAL.txt** - Diagramas y arquitectura

## 🎯 Próximos Pasos Recomendados

### 1. Integrar con PollingService

Modificar `src/polling_service.py`:

```python
from database import Database

class PollingService:
    def __init__(self, ...):
        self.db = Database()
    
    def _read_telemetry(self, unit_id):
        # ... lectura Modbus ...
        
        # Guardar en BD
        device = self.device_manager.get_device(unit_id)
        sensor_id = f"{device.alias}_{unit_id}"
        
        if 'angle_x_deg' in normalized:
            self.db.insert_measurement({
                'sensor_id': sensor_id,
                'type': 'tilt',
                'value': normalized['angle_x_deg'],
                'unit': 'deg',
                'quality': 'OK'
            })
```

### 2. Crear Motor de Alertas

Crear `src/alert_engine.py`:

```python
from database import Database

class AlertEngine:
    def __init__(self):
        self.db = Database()
    
    def check_alerts(self):
        sensors = self.db.get_all_sensors()
        for sensor in sensors:
            latest = self.db.get_measurements(
                sensor_id=sensor['sensor_id'], 
                limit=1
            )
            if not latest:
                continue
            
            value = latest[0]['value']
            
            if sensor['alarm_hi'] and value > sensor['alarm_hi']:
                self.db.insert_alert({
                    'level': 'ALARM',
                    'code': f"{sensor['type'].upper()}_HIGH",
                    'message': f"{value} > {sensor['alarm_hi']}",
                    'sensor_id': sensor['sensor_id'],
                    'rig_id': sensor['rig_id']
                })
```

### 3. Desarrollar Bridge ThingsBoard

Crear `src/thingsboard_bridge.py`:

```python
from database import Database
import requests

class ThingsBoardBridge:
    def __init__(self, tb_url, tb_token):
        self.tb_url = tb_url
        self.tb_token = tb_token
        self.db = Database()
    
    def sync_telemetry(self):
        unsent = self.db.get_unsent_measurements(limit=100)
        
        # Agrupar por sensor y publicar
        by_sensor = {}
        for m in unsent:
            sensor_id = m['sensor_id']
            if sensor_id not in by_sensor:
                by_sensor[sensor_id] = []
            by_sensor[sensor_id].append(m)
        
        for sensor_id, measurements in by_sensor.items():
            values = [m['value'] for m in measurements]
            
            telemetry = {
                'last_value': values[0],
                'min_value': min(values),
                'max_value': max(values),
                'avg_value': sum(values) / len(values)
            }
            
            # POST a ThingsBoard
            response = requests.post(
                f"{self.tb_url}/api/v1/{self.tb_token}/telemetry",
                json=telemetry
            )
            
            if response.status_code == 200:
                ids = [m['id'] for m in measurements]
                self.db.mark_as_sent(ids)
```

### 4. Añadir Endpoints API REST

En `src/app.py`:

```python
from database import Database

db = Database()

@app.route('/api/history/<sensor_id>')
def api_history(sensor_id):
    hours = request.args.get('hours', 24, type=int)
    limit = request.args.get('limit', 100, type=int)
    
    since = datetime.utcnow() - timedelta(hours=hours)
    data = db.get_measurements(sensor_id=sensor_id, since=since, limit=limit)
    
    return jsonify({
        'status': 'ok',
        'sensor_id': sensor_id,
        'hours': hours,
        'data': data
    })

@app.route('/api/alerts')
def api_alerts():
    ack = request.args.get('ack', None)
    if ack is not None:
        ack = ack.lower() in ('true', '1', 'yes')
    
    alerts = db.get_alerts(ack=ack, limit=100)
    return jsonify({'status': 'ok', 'alerts': alerts})

@app.route('/api/database/stats')
def api_database_stats():
    stats = db.get_db_stats()
    return jsonify({'status': 'ok', 'stats': stats})
```

## 🐛 Troubleshooting

### Error: "No module named 'database'"

**Solución:** Asegúrate de estar en el directorio correcto o añadir src/ al path:

```python
import sys
sys.path.insert(0, 'src')
from database import Database
```

### Error: "database is locked"

**Causa:** Otra conexión tiene la BD bloqueada.

**Solución:** El módulo ya usa context managers, pero puedes aumentar el timeout:

```python
# En database.py, _get_connection():
conn = sqlite3.connect(self.db_path, timeout=10.0)
```

### BD crece demasiado

**Solución:** Ejecutar limpieza periódica:

```python
db.cleanup_old_data(days=30)
```

O desde terminal:

```bash
python3 -c "from src.database import Database; db = Database(); db.cleanup_old_data(30)"
```

## ✨ Características Destacables

1. ✅ **Idempotente:** `init_db()` puede ejecutarse múltiples veces
2. ✅ **Portable:** Un solo archivo SQLite, sin dependencias externas
3. ✅ **Eficiente:** Índices optimizados para consultas frecuentes
4. ✅ **Robusto:** Context managers, transacciones ACID
5. ✅ **Completo:** API CRUD para sensores, medidas y alertas
6. ✅ **Probado:** 6 tests unitarios con 100% éxito
7. ✅ **Documentado:** Guías, ejemplos y diagramas

## 📞 Soporte

Para más información, consulta:
- `README_DATABASE.md` - Documentación completa
- `RESUMEN_DATABASE.md` - Resumen ejecutivo
- `ARQUITECTURA_DATABASE_VISUAL.txt` - Diagramas

---

**Estado:** ✅ **COMPLETADO Y VERIFICADO**  
**Versión:** 1.0  
**Fecha:** 3 de diciembre de 2025  
**Autor:** Edge Layer - TFM Supervisor de Cargas
