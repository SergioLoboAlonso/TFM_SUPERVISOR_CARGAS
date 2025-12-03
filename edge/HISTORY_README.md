# 📈 Historial - Visualización de Datos Históricos

## Descripción

La ventana **History** es una interfaz web completa para visualizar y analizar datos históricos almacenados en la base de datos SQLite del Edge Layer. Permite supervisar telemetría pasada incluso cuando los dispositivos están apagados o no están siendo monitoreados activamente.

## 🎯 Características Principales

### 1. **Visualización Jerárquica**
- **Dispositivos**: Lista de todos los dispositivos registrados (Unit ID, Alias, Capabilities)
- **Sensores**: Sensores disponibles para cada dispositivo seleccionado
- **Datos**: Visualización gráfica y tabular de medidas históricas

### 2. **Rangos Temporales**
- **Predefinidos**: 1 hora, 6 horas, 24 horas, 7 días, 30 días
- **Personalizado**: Selección de fecha/hora exacta (inicio y fin)

### 3. **Análisis en Tiempo Real**
- **Estadísticas**: Mínimo, Máximo, Promedio, Cantidad de muestras
- **Gráfico interactivo**: Chart.js con zoom y tooltips
- **Tabla de datos**: Listado completo con scroll

### 4. **Persistencia de Datos**
- Los datos permanecen en la BD incluso si:
  - El dispositivo se apaga
  - Se reinicia el servicio Edge
  - No hay supervisión activa
- Retención configurable (por defecto: 30 días)

## 🚀 Uso

### Acceso Web

Navega a: **http://localhost:8080/history**

### Flujo de Trabajo

1. **Seleccionar dispositivo** (columna izquierda)
   - Haz clic en cualquier tarjeta de dispositivo
   - Se muestran sus sensores y capabilities

2. **Seleccionar sensor**
   - Haz clic en el badge del sensor que deseas visualizar
   - Aparecen los controles de rango temporal

3. **Elegir rango temporal**
   - Usa los botones predefinidos (1h, 6h, 24h, 7d, 30d)
   - O ingresa fechas personalizadas y haz clic en "Aplicar"

4. **Analizar datos**
   - **Gráfico**: Visualiza tendencias y patrones
   - **Estadísticas**: Ve min/max/avg del período
   - **Tabla**: Consulta valores exactos con timestamps

## 📊 API REST

### Endpoints Disponibles

#### 1. Estadísticas de BD
```bash
GET /api/history/stats
```

**Respuesta:**
```json
{
  "db_path": "edge_measurements.db",
  "db_size_mb": 1.12,
  "device_count": 2,
  "sensor_count": 9,
  "measurement_count": 7838,
  "alert_count": 0
}
```

#### 2. Lista de Dispositivos
```bash
GET /api/history/devices
```

**Respuesta:**
```json
{
  "devices": [
    {
      "unit_id": 1,
      "alias": "WindMeter",
      "capabilities": "[\"RS485\", \"Wind\"]",
      "rig_id": "RIG_01",
      "vendor_code": "0x4C6F",
      "last_seen": "2025-12-03T19:46:53Z"
    }
  ]
}
```

#### 3. Sensores de un Dispositivo
```bash
GET /api/history/sensors/<unit_id>
```

**Respuesta:**
```json
{
  "device": { ... },
  "sensors": [
    {
      "sensor_id": "UNIT_2_TILT_X",
      "unit_id": 2,
      "type": "tilt",
      "unit": "deg",
      "alarm_lo": -10.0,
      "alarm_hi": 10.0
    }
  ]
}
```

#### 4. Datos Históricos
```bash
# Por horas desde ahora
GET /api/history/data/<sensor_id>?hours=24

# Rango personalizado
GET /api/history/data/<sensor_id>?start=2025-12-03T10:00:00Z&end=2025-12-03T18:00:00Z
```

**Respuesta:**
```json
{
  "sensor_id": "UNIT_2_TILT_X",
  "unit": "deg",
  "stats": {
    "count": 653,
    "min": 0.57,
    "max": 0.79,
    "avg": 0.69
  },
  "measurements": [
    {
      "timestamp": "2025-12-03T19:38:13Z",
      "sensor_id": "UNIT_2_TILT_X",
      "value": 0.69,
      "unit": "deg",
      "quality": "OK"
    }
  ]
}
```

## 🛠️ Estructura Técnica

### Frontend
- **Template**: `templates/history.html`
- **JavaScript**: `static/js/history.js`
- **Librería de gráficos**: Chart.js 4.4.0
- **Estilo**: Bootstrap 5.3

### Backend
- **Rutas**: Definidas en `src/app.py`
  - `/history` → Vista principal
  - `/api/history/*` → Endpoints REST
- **Base de datos**: `src/database.py`
  - Métodos optimizados para consultas históricas
  - Índices para rendimiento

### Base de Datos

Estructura jerárquica:

```
devices (dispositivos físicos)
  ├─ unit_id (PK)
  ├─ alias, capabilities, rig_id
  └─ last_seen
  
sensors (sensores lógicos)
  ├─ sensor_id (PK)
  ├─ unit_id (FK → devices)
  ├─ type, unit, register
  └─ alarm_lo, alarm_hi
  
measurements (telemetría)
  ├─ sensor_id (FK → sensors)
  ├─ timestamp, value
  └─ quality, sent_to_cloud
```

## 💡 Casos de Uso

### 1. Análisis Retrospectivo
Dispositivo se apagó a las 10:00. A las 15:00 quieres ver qué pasó:
- Selecciona el dispositivo
- Elige rango personalizado: 09:00 - 11:00
- Visualiza el comportamiento antes del apagado

### 2. Detección de Tendencias
Analizar comportamiento de un sensor durante 7 días:
- Selecciona sensor de temperatura
- Rango: 7 días
- Identifica patrones horarios o diarios

### 3. Verificación de Umbrales
Revisar si hubo valores fuera de rango:
- Selecciona sensor con umbrales configurados
- Rango amplio (30 días)
- Tabla muestra todos los valores, incluyendo WARN/ALARM

### 4. Exportación de Datos
Necesitas los datos en Excel/CSV:
- Visualiza la tabla de datos
- Selecciona y copia (Ctrl+C)
- Pega en Excel o Google Sheets

## 🔧 Configuración

### Retención de Datos

Por defecto: 30 días. Modificar en `src/database.py`:

```python
DEFAULT_RETENTION_DAYS = 30  # Cambiar según necesidad
```

### Límite de Consultas

Por defecto: 10,000 medidas. Modificar en `src/app.py`:

```python
measurements = database.get_measurements(
    sensor_id=sensor_id,
    since=since,
    limit=10000  # Aumentar si es necesario
)
```

## 📱 Compatibilidad

- **Navegadores**: Chrome, Firefox, Edge, Safari (últimas 2 versiones)
- **Resoluciones**: Desktop, Tablet, Mobile (responsive)
- **ThingsBoard Edge**: Estructura compatible para sincronización

## ⚡ Rendimiento

### Optimizaciones Implementadas

1. **Índices en BD**:
   - `idx_measurements_timestamp`: Consultas por fecha
   - `idx_measurements_sensor_id`: Consultas por sensor
   - `idx_sensors_unit_id`: Sensores por dispositivo

2. **Límites de consulta**: Evita sobrecarga con datasets grandes

3. **Carga diferida**: Solo se cargan datos al seleccionar sensor

4. **Gráficos optimizados**: Chart.js con decimación automática

### Métricas Típicas

- **Consulta 24h (1 sensor)**: ~50ms
- **Consulta 7 días (1 sensor)**: ~200ms
- **Carga lista dispositivos**: <10ms
- **BD de 1GB**: ~100,000 medidas/segundo

## 🐛 Troubleshooting

### No aparecen dispositivos
**Causa**: BD vacía o discovery no ejecutado  
**Solución**: Ejecuta discovery desde `/diagnostic`

### Error "Database not available"
**Causa**: BD no inicializada  
**Solución**: Verifica logs del servicio
```bash
sudo journalctl -u tfm-edge.service -n 50
```

### Gráfico no se renderiza
**Causa**: No hay datos en el rango seleccionado  
**Solución**: Amplía el rango temporal o verifica que el sensor tenga datos

### Datos muy antiguos
**Causa**: Retención configurada  
**Solución**: Aumenta `DEFAULT_RETENTION_DAYS` o desactiva limpieza automática

## 📚 Referencias

- [Chart.js Documentation](https://www.chartjs.org/docs/latest/)
- [Bootstrap 5 Docs](https://getbootstrap.com/docs/5.3/)
- [SQLite Time Series](https://www.sqlite.org/lang_datefunc.html)

---

✅ **La ventana History permite supervisión completa de datos históricos sin perder información cuando los dispositivos se apagan o no están siendo monitoreados.**
