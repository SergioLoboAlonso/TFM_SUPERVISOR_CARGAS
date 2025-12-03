# Guía de Auto-Discovery de Sensores

## Descripción General

El sistema de **auto-discovery** permite que los dashboards de ThingsBoard se actualicen automáticamente cuando se detectan nuevos dispositivos o sensores, sin necesidad de reconfigurar manualmente los widgets.

## Características

### 1. **Eventos de Conectividad**
- Publicación automática cuando dispositivos se conectan/desconectan
- Topics ThingsBoard Gateway:
  - `v1/gateway/connect` - Dispositivo online
  - `v1/gateway/disconnect` - Dispositivo offline
- Detección inteligente: 3 errores consecutivos → offline

### 2. **Inventario de Sensores**
- Publicación automática de lista completa de dispositivos y sensores
- Se actualiza cuando:
  - Discovery inicial completa
  - Nuevos dispositivos detectados
  - Cambios en configuración
- Topic: `v1/gateway/attributes` (como atributos del Gateway)

### 3. **Atributos de Dispositivo**
- Publicación automática de metadatos:
  - `owner`: Alias/nombre del dispositivo
  - `unit_id`: ID Modbus
  - `capabilities`: Lista de sensores soportados
  - `rig_id`: Identificador del rig/ubicación

## Arquitectura

```
┌─────────────────┐
│  Edge Gateway   │
│  (Raspberry Pi) │
└────────┬────────┘
         │
         │ Discovery
         ▼
┌─────────────────┐
│ Device Manager  │
│  (detecta 2     │
│   dispositivos) │
└────────┬────────┘
         │
         │ 1. Registra en BD
         │ 2. Publica Atributos
         │ 3. Publica Inventario
         ▼
┌─────────────────┐      MQTT       ┌──────────────────┐
│  MQTT Bridge    │─────────────────>│  ThingsBoard     │
│                 │                  │  Cloud Gateway   │
└─────────────────┘                  └──────────────────┘
         │                                    │
         │ Telemetry                         │
         │ Connectivity Events                │
         │ Inventory Updates                  │
         │                                    ▼
         │                          ┌──────────────────┐
         └─────────────────────────>│   Dashboards     │
                                    │  (auto-update)   │
                                    └──────────────────┘
```

## Flujo de Datos

### Discovery Inicial
1. **Escaneo de Red** (`start_initial_discovery()`)
   - Detecta dispositivos Modbus en red (unit_id 1-10)
   - Identifica capabilities (MPU6050, Wind, Load)

2. **Registro en Base de Datos** (`_register_sensors_to_database()`)
   - Crea entrada en tabla `devices`
   - Crea sensores individuales en tabla `sensors`:
     - `UNIT_1_TILT_X`, `UNIT_1_TILT_Y`, `UNIT_1_TEMP`
     - `UNIT_1_WIND_SPEED`, `UNIT_1_WIND_DIR`
     - `UNIT_1_LOAD`
   - Configura umbrales de alarma predeterminados

3. **Publicación a ThingsBoard**
   - **Atributos** → `mqtt_bridge.publish_device_attributes()`
     ```json
     {
       "Sensor_Unit1": {
         "owner": "WindMeter",
         "unit_id": 1,
         "capabilities": "Identify, RS485, Wind",
         "rig_id": "RIG_01"
       }
     }
     ```
   
   - **Conectividad** → `mqtt_bridge.publish_device_connectivity()`
     ```json
     {
       "device": "Sensor_Unit1"
     }
     ```
     Topic: `v1/gateway/connect`

   - **Inventario** → `mqtt_bridge.publish_active_sensors_list()`
     ```json
     {
       "EdgeGateway": {
         "active_devices_count": 2,
         "active_devices": "[{\"name\":\"Sensor_Unit1\",\"alias\":\"WindMeter\",...}]",
         "all_sensors": "[{\"sensor_id\":\"UNIT_1_WIND_SPEED\",\"device\":\"Sensor_Unit1\",...}]",
         "last_inventory_update": "2025-12-03T21:00:00Z"
       }
     }
     ```

### Detección de Cambios de Estado

**Dispositivo Online → Offline:**
```
Polling tick → Error lectura Modbus
  ↓
Error #1 → Backoff 5s
Error #2 → Backoff 10s
Error #3 → OFFLINE
  ↓
publish_device_connectivity(device, connected=False)
  ↓
ThingsBoard recibe disconnect event
  ↓
Dashboard actualiza status widget (🔴 OFFLINE)
```

**Dispositivo Offline → Online:**
```
Polling tick → Lectura exitosa
  ↓
Detecta cambio: was_offline=True, now=OK
  ↓
publish_device_connectivity(device, connected=True)
  ↓
ThingsBoard recibe connect event
  ↓
Dashboard actualiza status widget (🟢 ONLINE)
```

## API REST

### Publicar Inventario Manualmente
```bash
curl -X POST http://localhost:8080/api/mqtt/inventory/publish
```

**Respuesta:**
```json
{
  "status": "ok",
  "message": "Inventario publicado a ThingsBoard correctamente"
}
```

**Uso:**
- Sincronizar después de cambios de configuración
- Recuperación después de desconexiones MQTT
- Testing/debugging de dashboards

## Configuración en ThingsBoard

### 1. Ver Atributos del Gateway

1. Ir a **Devices** → `EdgeGateway`
2. Pestaña **Attributes** → **Server attributes**
3. Buscar:
   - `active_devices_count`
   - `active_devices` (JSON string)
   - `all_sensors` (JSON string)
   - `last_inventory_update`

### 2. Ver Atributos de Dispositivo

1. Ir a **Devices** → `Sensor_Unit1` o `Sensor_Unit2`
2. Pestaña **Attributes** → **Server attributes**
3. Buscar:
   - `owner`: Alias del dispositivo
   - `capabilities`: Lista de sensores
   - `unit_id`: ID Modbus
   - `rig_id`: Ubicación/rig

### 3. Crear Widget con Lista Dinámica de Sensores

**Widget: "Entities Table" o "Devices Table"**

1. Crear nuevo dashboard
2. Agregar widget **"Entities table"**
3. Configurar:
   - **Entity alias**: `All devices`
     - Type: `Device type`
     - Device type: `default`
   
   - **Columns**:
     - `Device name` → `${entityName}`
     - `Owner` → `${owner}`
     - `Unit ID` → `${unit_id}`
     - `Capabilities` → `${capabilities}`
     - `Status` → `${active}` (last telemetry)

4. El widget se actualiza automáticamente cuando:
   - Se descubren nuevos dispositivos
   - Cambia estado online/offline
   - Se modifican atributos

### 4. Crear Selector Dinámico de Sensores

**Widget: "Timeseries Line Chart" con selector de dispositivo**

1. Agregar widget **"Timeseries - Flot"**
2. Configurar **Entity alias**:
   - Name: `Selected Device`
   - Type: `Entity from dashboard state`
   - State entity parameter: `device`

3. Configurar **Datasources**:
   - Keys: `tilt_x`, `tilt_y`, `temperature`, `wind_speed`
   - Agregation: `NONE`

4. Agregar **Dashboard state** (esquina superior):
   - Variable: `device`
   - Default: `Sensor_Unit1`
   - Type: `Entity`

5. Resultado:
   - Selector dropdown con todos los dispositivos
   - Gráfica se actualiza automáticamente al cambiar dispositivo
   - No requiere reconfiguración cuando se agregan nuevos sensores

## Eventos MQTT

### Topic: `v1/gateway/connect`
```json
{
  "device": "Sensor_Unit1"
}
```

### Topic: `v1/gateway/disconnect`
```json
{
  "device": "Sensor_Unit2"
}
```

### Topic: `v1/gateway/attributes`
```json
{
  "EdgeGateway": {
    "active_devices_count": 2,
    "active_devices": "[...]",
    "all_sensors": "[...]",
    "last_inventory_update": "2025-12-03T21:05:00Z"
  }
}
```

## Logs

### Discovery Completado
```
✅ Discovery completado: 2 dispositivos encontrados
📝 Registrando dispositivo 1 (WindMeter), caps=['Wind', 'Identify']
   ✅ Sensores Wind registrados para unit 1
📝 Registrando dispositivo 2 (PA_L), caps=['MPU6050', 'Wind', 'Identify']
   ✅ Sensores MPU6050 registrados para unit 2
   ✅ Sensores Wind registrados para unit 2
✅ Total de 2 dispositivos registrados en BD
```

### Publicación de Inventario
```
📋 Atributos publicados para Sensor_Unit1: {'owner': 'WindMeter', ...}
📋 Atributos publicados para Sensor_Unit2: {'owner': 'PA_L', ...}
🔌 Dispositivo Sensor_Unit1 ✅ conectado
🔌 Dispositivo Sensor_Unit2 ✅ conectado
📊 Inventario publicado: 2 dispositivos, 8 sensores
📤 Inventario publicado a ThingsBoard: 2 dispositivos
```

### Eventos de Conectividad
```
# Dispositivo online
🟢 Dispositivo unit_2 detectado como ONLINE
🔌 Dispositivo Sensor_Unit2 ✅ conectado

# Dispositivo offline
🔴 Dispositivo unit_1 detectado como OFFLINE
🔌 Dispositivo Sensor_Unit1 ❌ desconectado
```

## Troubleshooting

### Inventario no aparece en ThingsBoard
1. Verificar logs: `tail -f /tmp/edge_app.log | grep Inventario`
2. Verificar conexión MQTT: `grep "Conectado a broker" /tmp/edge_app.log`
3. Republicar manualmente: `curl -X POST localhost:8080/api/mqtt/inventory/publish`

### Atributos no visibles
1. Ir a ThingsBoard → Devices → EdgeGateway → Attributes
2. Si no existe `EdgeGateway`, publicar inventario manualmente
3. Verificar permisos de Gateway token

### Widgets no se actualizan
1. Verificar que widget usa **Entity alias** dinámico, no entidad fija
2. Recargar dashboard (F5)
3. Verificar que datasource usa **"latest telemetry"** o **"timeseries"**

## Mejoras Futuras

- [ ] Publicar cambios de configuración automáticamente
- [ ] Notificaciones push cuando nuevo dispositivo se conecta
- [ ] Dashboard template auto-generado con todos los sensores
- [ ] API para consultar inventario sin ThingsBoard
- [ ] Soporte para múltiples Gateways/Edges
- [ ] Grupos/categorías de sensores

## Referencias

- [ThingsBoard Gateway API](https://thingsboard.io/docs/reference/gateway-mqtt-api/)
- [MQTT Integration Guide](MQTT_INTEGRATION.md)
- [ThingsBoard Setup](THINGSBOARD_SETUP.md)
