# Especificación Edge Layer — Supervisor de Cargas

## 1. Propósito y Responsabilidades 

### 1.1. Objetivo General
El **Edge Layer** es el intermediario entre los dispositivos Modbus RTU (firmware Arduino) y sistemas externos (MQTT, FIWARE, almacenamiento local). Sus responsabilidades son:

- **Comunicación Modbus RTU**: leer/escribir registros de dispositivos esclavos vía RS-485.
- **Normalización de datos**: convertir registros Modbus (enteros escalados) a unidades físicas (°, °C, mg, kg).
- **Publicación MQTT**: enviar telemetría normalizada a broker MQTT con formato JSON estándar.
- **API REST local**: exponer endpoints HTTP para consulta, configuración y comandos (opcional).
- **Gestión de identidad**: descubrir dispositivos, leer alias, UnitID, versiones HW/FW.
- **Logging y diagnóstico**: registrar errores, excepciones Modbus, timeouts, CRC, etc.

### 1.2. Fuera de Alcance (No Hace)
- **No almacena históricos** (lo hace FIWARE/InfluxDB/etc.).
- **No hace análisis avanzado** (eso es responsabilidad de capa superior).
- **No controla lógica de negocio** (el firmware decide cuándo leer sensores; Edge solo consulta).

---

## 2. Arquitectura del Edge

### 2.1. Diagrama General

```
┌─────────────────────────────────────────────────────────────┐
│                      Edge Application                        │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │          Web UI (Flask + HTML/JS)                  │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────┐ │    │
│  │  │   Dashboard  │  │ Configuration│  │ Polling  │ │    │
│  │  │   (Home)     │  │   Window     │  │  Window  │ │    │
│  │  └──────┬───────┘  └──────┬───────┘  └────┬─────┘ │    │
│  └─────────┼──────────────────┼───────────────┼───────┘    │
│            │                  │               │             │
│  ┌─────────▼──────────────────▼───────────────▼───────┐    │
│  │              REST API Backend (Flask)              │    │
│  └─────────┬──────────────────┬───────────────┬───────┘    │
│            │                  │               │             │
│  ┌─────────▼──────┐  ┌───────▼──────┐  ┌────▼────────┐    │
│  │ Device Manager │  │Modbus Client │  │Data Normaliz│    │
│  │  & Discovery   │  │  (pymodbus)  │  │    -er      │    │
│  └────────────────┘  └───────┬──────┘  └─────────────┘    │
│                              │                              │
│  ┌───────────────────────────▼──────────────────────┐      │
│  │         MQTT Publisher (Optional)                │      │
│  └──────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────┘
                      │                    │
                      ▼                    ▼
                RS-485 Bus           MQTT Broker
               (Modbus RTU)       (Mosquitto/Cloud)
```

### 2.2. Arquitectura de 3 Ventanas (Web UI)

#### **Ventana 1: Dashboard (Home/Principal)**
**Propósito**: Vista inicial con información del adaptador USB-RS485 y navegación.

**Elementos UI**:
- Info del adaptador:
  - Puerto detectado (ej. `/dev/ttyUSB0`)
  - Baudrate configurado (ej. 115200)
  - Estado de conexión (🟢 Conectado / 🔴 Desconectado)
  - Estadísticas globales:
    - Total de tramas TX/RX
    - Errores CRC
    - Dispositivos activos
- Botones de navegación:
  - 🔧 **"Configuración"** → Va a ventana de configuración
  - 📊 **"Polling en Vivo"** → Va a ventana de polling

**Actualización**: Estática (solo se refresca al reconectar adaptador).

---

#### **Ventana 2: Configuración (Configuration Window)**
**Propósito**: Gestión de dispositivos, discovery, identity management.

**Elementos UI**:

1. **Panel de Discovery**:
   - Input: Rango de UnitIDs a escanear (ej. 1..10)
   - Botón: **"Escanear Red"** → Ejecuta discovery, muestra progreso
   - Resultado: Lista de dispositivos encontrados con:
     - UnitID
     - Vendor/Product
     - HW/FW version
     - Alias actual
     - Estado (online/offline)

2. **Panel de Gestión por Dispositivo** (tabla editable):
   - Columnas:
     - UnitID (actual)
     - Alias (editable, input text)
     - Acciones:
       - 🔦 **Identify** → Parpadea LED por N segundos
       - 💾 **Guardar Alias** → Escribe alias a EEPROM vía 0x10 + 0xA55A
       - 🔄 **Cambiar UnitID** → Abre modal para nuevo UnitID + save

3. **Botón de navegación**:
   - ⬅️ **"Volver a Dashboard"**

**Actualización**: On-demand (solo al hacer discovery o refrescar manualmente).

---

#### **Ventana 3: Polling (Live Telemetry Window)**
**Propósito**: Monitoreo en tiempo real de telemetría de dispositivos activos.

**Elementos UI**:

1. **Controles de Polling**:
   - Toggle: **"Iniciar/Pausar Polling"**
   - Input: Intervalo de polling (segundos, ej. 5s)
   - Checkbox: Dispositivos a monitorear (multi-select de lista de UnitIDs)

2. **Panel de Telemetría en Tiempo Real** (actualización automática):
   - Tarjetas por dispositivo (grid layout):
     - **Header**: UnitID, Alias, Timestamp de última lectura
     - **Body**: Valores actuales con iconos:
       - 📐 Ángulo X/Y (°)
       - 🌡️ Temperatura (°C)
       - 📈 Aceleración X/Y/Z (g)
       - 🔄 Giroscopio X/Y/Z (°/s)
       - ⚖️ Peso (kg)
       - 🔢 Contador de muestras
     - **Footer**: Estado (🟢 OK / 🟡 Degraded / 🔴 Timeout)

3. **Gráficos en Tiempo Real** (opcional, fase 2):
   - Chart.js / Plotly para ángulos, temperatura (últimos 60s)

4. **Log de Eventos**:
   - Scroll list con últimos 50 eventos:
     - "UnitID 2: Telemetry received"
     - "UnitID 3: Timeout after 3 retries"
     - "UnitID 2: CRC error"

5. **Botón de navegación**:
   - ⬅️ **"Volver a Dashboard"**

**Actualización**: Automática (WebSocket o SSE) cada N segundos según intervalo configurado.

---

### 2.3. Módulos Backend (Python)

| Módulo                  | Archivo Sugerido       | Responsabilidad                                                                 |
|-------------------------|------------------------|---------------------------------------------------------------------------------|
| **Modbus Client**       | `modbus_client.py`     | pymodbus wrapper, lectura/escritura registros, timeouts, excepciones           |
| **Device Manager**      | `device_manager.py`    | Gestión de dispositivos, caché de identidad, discovery, estado online/offline  |
| **Data Normalizer**     | `data_normalizer.py`   | Conversión de registros Modbus (escalados) a unidades físicas                  |
| **MQTT Publisher**      | `mqtt_publisher.py`    | Publicar telemetría a MQTT (opcional, fase 2)                                  |
| **Polling Service**     | `polling_service.py`   | Thread/async loop para polling automático, encola telemetría para UI           |
| **Config Manager**      | `config.py`            | Carga .env, valida configuración, expone settings globales                      |
| **Logger**              | `logger.py`            | Logging estructurado (file + console), niveles configurables                    |
| **Flask App**           | `app.py`               | REST API + Web UI, rutas para dashboard, config, polling                        |
| **WebSocket Handler**   | `websocket.py`         | (Opcional) Socket.IO para push de telemetría en tiempo real a UI                |

---

## 3. Protocolo Modbus RTU: Mapa de Registros

### 3.1. Holding Registers (Función 0x03/0x06/0x10)

#### Información de Dispositivo (Solo Lectura desde Edge)
| Dirección | Símbolo                | Tipo  | Unidad        | Descripción                          |
|-----------|------------------------|-------|---------------|--------------------------------------|
| 0x0000    | `HR_INFO_VENDOR_ID`    | uint16| —             | Vendor ID (0x5446 = 'TF')            |
| 0x0001    | `HR_INFO_PRODUCTO_ID`  | uint16| —             | Product ID (0x4D30 = 'M0')           |
| 0x0002    | `HR_INFO_VERSION_HW`   | uint16| —             | HW version (major<<8 \| minor)       |
| 0x0003    | `HR_INFO_VERSION_FW`   | uint16| —             | FW version (major<<8 \| minor)       |
| 0x0004    | `HR_INFO_ID_UNIDAD`    | uint16| —             | Unit ID efectivo (eco)               |
| 0x0005    | `HR_INFO_CAPACIDADES`  | uint16| bitmask       | Capacidades (RS485, MPU, Identify)   |
| 0x0006    | `HR_INFO_UPTIME_S_LO`  | uint16| s             | Uptime LSW                           |
| 0x0007    | `HR_INFO_UPTIME_S_HI`  | uint16| s             | Uptime MSW                           |
| 0x0008    | `HR_INFO_ESTADO`       | uint16| bitmask       | Estado (OK, MPU_READY, CFG_DIRTY)    |
| 0x0009    | `HR_INFO_ERRORES`      | uint16| bitmask       | Errores (MPU_COMM, EEPROM, RANGE)    |

#### Configuración (Lectura/Escritura)
| Dirección | Símbolo                | Tipo  | Unidad        | Descripción                          |
|-----------|------------------------|-------|---------------|--------------------------------------|
| 0x0010    | `HR_CFG_BAUDIOS`       | uint16| código        | Solo lectura (fijado por compilación)|
| 0x0011    | `HR_CFG_MPU_FILTRO_HZ` | uint16| Hz            | Filtro MPU (5..200 Hz)               |
| 0x0012    | `HR_CMD_GUARDAR`       | uint16| comando       | 0xA55A=save to EEPROM                |
| 0x0013    | `HR_CMD_IDENT_SEGUNDOS`| uint16| s             | Identify timeout (0=stop)            |
| 0x0014    | `HR_CFG_ID_UNIDAD`     | uint16| 1..247        | Unit ID (R/W, persistente)           |

#### Diagnóstico (Solo Lectura)
| Dirección | Símbolo                   | Tipo  | Unidad        | Descripción                       |
|-----------|---------------------------|-------|---------------|-----------------------------------|
| 0x0020    | `HR_DIAG_TRAMAS_RX_OK`    | uint16| count         | Tramas RX OK                      |
| 0x0021    | `HR_DIAG_RX_CRC_ERROR`    | uint16| count         | Tramas RX con CRC malo            |
| 0x0022    | `HR_DIAG_RX_EXCEPCIONES`  | uint16| count         | Excepciones enviadas              |
| 0x0023    | `HR_DIAG_TRAMAS_TX_OK`    | uint16| count         | Tramas TX OK                      |
| 0x0024    | `HR_DIAG_DESBORDES_UART`  | uint16| count         | UART overruns                     |
| 0x0025    | `HR_DIAG_ULTIMA_EXCEPCION`| uint16| código        | Último código de excepción        |

#### Identidad Extendida (Solo Lectura, ASCII empaquetado)
| Dirección | Símbolo                   | Tipo  | Unidad        | Descripción                       |
|-----------|---------------------------|-------|---------------|-----------------------------------|
| 0x0026    | `HR_INFO_VENDOR_STR_LEN`  | uint16| bytes         | Longitud vendor name (0..8)       |
| 0x0027..2A| `HR_INFO_VENDOR_STR0..3`  | uint16| ASCII         | Vendor name (2B/reg, big-endian)  |
| 0x002B    | `HR_INFO_PRODUCT_STR_LEN` | uint16| bytes         | Longitud product name (0..8)      |
| 0x002C..2F| `HR_INFO_PRODUCT_STR0..3` | uint16| ASCII         | Product name (2B/reg)             |

#### Alias del Dispositivo (Lectura y Escritura 0x10)
| Dirección | Símbolo                | Tipo  | Unidad        | Descripción                          |
|-----------|------------------------|-------|---------------|--------------------------------------|
| 0x0030    | `HR_ID_ALIAS_LEN`      | uint16| bytes         | Longitud alias (0..64)               |
| 0x0031..50| `HR_ID_ALIAS0..31`     | uint16| ASCII         | Alias ASCII (2B/reg, big-endian)     |

### 3.2. Input Registers (Función 0x04 — Solo Lectura)

#### Medidas de Sensores
| Dirección | Símbolo                     | Tipo  | Escala       | Unidad Real  | Descripción                    |
|-----------|-----------------------------|-------|--------------|--------------|--------------------------------|
| 0x0000    | `IR_MED_ANGULO_X_CDEG`      | int16 | ×100         | °            | Ángulo X en centésimas de °    |
| 0x0001    | `IR_MED_ANGULO_Y_CDEG`      | int16 | ×100         | °            | Ángulo Y en centésimas de °    |
| 0x0002    | `IR_MED_TEMPERATURA_CENTI`  | int16 | ×100         | °C           | Temperatura en centésimas °C   |
| 0x0003    | `IR_MED_ACEL_X_mG`          | int16 | mg           | g            | Aceleración X (mili-g)         |
| 0x0004    | `IR_MED_ACEL_Y_mG`          | int16 | mg           | g            | Aceleración Y (mili-g)         |
| 0x0005    | `IR_MED_ACEL_Z_mG`          | int16 | mg           | g            | Aceleración Z (mili-g)         |
| 0x0006    | `IR_MED_GIRO_X_mdps`        | int16 | mdps         | °/s          | Giroscopio X (mili-dps)        |
| 0x0007    | `IR_MED_GIRO_Y_mdps`        | int16 | mdps         | °/s          | Giroscopio Y (mili-dps)        |
| 0x0008    | `IR_MED_GIRO_Z_mdps`        | int16 | mdps         | °/s          | Giroscopio Z (mili-dps)        |
| 0x0009    | `IR_MED_MUESTRAS_LO`        | uint16| —            | count        | Contador muestras LSW          |
| 0x000A    | `IR_MED_MUESTRAS_HI`        | uint16| —            | count        | Contador muestras MSW          |
| 0x000B    | `IR_MED_FLAGS_CALIDAD`      | uint16| bitmask      | —            | Flags de calidad (futuro)      |
| 0x000C    | `IR_MED_PESO_KG`            | int16 | kg (sin dec.)| kg           | Peso/carga en kg               |

---

## 4. Flujos de Operación

### 4.1. Arranque del Edge

```
1. Cargar configuración (.env, config.yaml):
   - Puerto serie (ej. /dev/ttyUSB0) → autodetección vía glob('/dev/tty.usb*')
   - Baudrate (115200)
   - MQTT broker (host, port, user, pass) [opcional]
   - Intervalo de polling por defecto (ej. 5s)
   - Límites de discovery (UnitID 1..10)

2. Inicializar Modbus Client:
   - Conectar a puerto serie
   - Configurar timeout (ej. 1s por trama)
   - Leer estadísticas del adaptador (si disponible)

3. Inicializar Flask App:
   - Cargar rutas: /, /config, /polling
   - Inicializar WebSocket/SSE para push de telemetría (opcional)
   - Servir en 0.0.0.0:8080

4. Mostrar Dashboard:
   - Renderizar página principal con info del adaptador
   - Estado: "Listo para configurar o iniciar polling"

5. Usuario navega a configuración o polling según necesidad
```

---

### 4.2. Flujo de Configuración (Configuration Window)

#### 4.2.1. Discovery de Dispositivos

**Trigger**: Usuario pulsa **"Escanear Red"** con rango UnitID 1..10.

```
1. Backend recibe POST /api/discover con params: {unit_id_min: 1, unit_id_max: 10}

2. Ejecutar discovery:
   PARA unit_id = unit_id_min HASTA unit_id_max:
     a) Enviar Modbus 0x03 a HR_INFO_VENDOR_ID (addr=0x0000, count=1)
     b) Si respuesta válida en <200ms:
        - Dispositivo encontrado
        - Leer bloque de identidad:
          * HR_INFO_VENDOR_ID..HR_INFO_ERRORES (0x0000..0x0009)
          * HR_INFO_VENDOR_STR* (0x0026..0x002F, si CAPABILITIES indica string support)
          * HR_ID_ALIAS* (0x0030..0x0050)
        - Parsear strings ASCII (big-endian, 2B/reg)
        - Cachear en DeviceManager:
          {
            unit_id: X,
            vendor_id: 0x5446,
            product_id: 0x4D30,
            hw_version: "0.3.2",
            fw_version: "0.1.1",
            alias: "Sensor-Piso-1",
            capabilities: ["RS485", "MPU6050", "Identify"],
            status: "online",
            last_seen: timestamp
          }
     c) Si timeout o excepción:
        - Continuar al siguiente UnitID
   FIN PARA

3. Devolver a frontend: JSON con lista de dispositivos encontrados

4. Frontend actualiza tabla de dispositivos en UI

5. Usuario puede ahora editar alias, hacer identify, o cambiar UnitID
```

---

#### 4.2.2. Identify Device (Blink LED)

**Trigger**: Usuario pulsa botón 🔦 **Identify** en fila de dispositivo.

```
1. Frontend envía POST /api/devices/{unit_id}/identify con body: {duration_sec: 10}

2. Backend:
   a) Validar unit_id existe en caché
   b) Escribir Modbus 0x06 a HR_CMD_IDENT_SEGUNDOS (0x0013) = 10
   c) Firmware inicia parpadeo LED por 10 segundos
   d) Responder a frontend: {status: "ok", message: "LED parpadeando 10s"}

3. Frontend muestra notificación: "Dispositivo X identificándose..."

4. (Opcional) Frontend desactiva botón Identify por 10s para evitar spam
```

---

#### 4.2.3. Guardar Alias a EEPROM

**Trigger**: Usuario edita alias en input text y pulsa 💾 **Guardar Alias**.

```
1. Frontend envía PUT /api/devices/{unit_id}/alias con body: {alias: "Nuevo-Alias"}

2. Backend:
   a) Validar alias (longitud 0..64, solo ASCII imprimible)
   b) Construir trama Modbus 0x10 (Write Multiple):
      - Addr: HR_ID_ALIAS_LEN (0x0030)
      - Count: 1 + ceil(len(alias)/2)
      - Data:
        * Registro 0: len(alias)
        * Registros 1..N: alias empaquetado (2B/reg, MSB→LSB)
        * Rellenar con 0x00 si longitud impar
   c) Enviar trama 0x10
   d) Si respuesta OK:
      - Escribir Modbus 0x06 a HR_CMD_GUARDAR (0x0012) = 0xA55A
      - Esperar confirmación (firmware guarda a EEPROM)
      - Actualizar caché local: device.alias = "Nuevo-Alias"
      - Responder: {status: "ok", message: "Alias guardado"}
   e) Si error:
      - Responder: {status: "error", message: "Timeout/CRC error"}

3. Frontend:
   - Actualiza celda de tabla con nuevo alias
   - Muestra notificación: "Alias guardado correctamente" (verde)
   - Si error: "Error al guardar alias" (rojo)
```

---

#### 4.2.4. Cambiar Unit ID

**Trigger**: Usuario pulsa 🔄 **Cambiar UnitID** → Modal con input de nuevo UnitID.

```
1. Frontend envía PUT /api/devices/{unit_id}/unit_id con body: {new_unit_id: 5}

2. Backend:
   a) Validar new_unit_id (rango 1..247, no colisiona con otro dispositivo activo)
   b) Escribir Modbus 0x06 a HR_CFG_ID_UNIDAD (0x0014) = 5
   c) Escribir Modbus 0x06 a HR_CMD_GUARDAR (0x0012) = 0xA55A
   d) Si OK:
      - Actualizar caché: device.unit_id = 5 (cambiar key del diccionario)
      - Responder: {status: "ok", message: "UnitID cambiado a 5"}
   e) Si error:
      - Responder: {status: "error", message: "Timeout/collision"}

3. Frontend:
   - Actualiza tabla (mueve fila a nueva posición ordenada por UnitID)
   - Muestra advertencia: "Dispositivo ahora responde en UnitID 5. Requiere re-scan para confirmar."

4. (Recomendación) Usuario debe hacer "Escanear Red" de nuevo para validar cambio
```

---

### 4.3. Flujo de Polling (Live Telemetry Window)

#### 4.3.1. Iniciar Polling

**Trigger**: Usuario pulsa **"Iniciar Polling"** con:
- Intervalo: 5s
- Dispositivos seleccionados: [2, 3] (checkboxes marcados)

```
1. Frontend envía POST /api/polling/start con body:
   {
     interval_sec: 5.0,
     unit_ids: [2, 3]
   }

2. Backend:
   a) Validar unit_ids existen en caché
   b) Crear PollingService thread/task:
      - Bucle infinito (hasta stop):
        * Para cada unit_id en [2, 3]:
          - Leer Input Registers (0x04, addr=0x0000, count=13)
          - Si OK:
            * Normalizar datos (escalados → unidades reales)
            * Construir payload:
              {
                unit_id: 2,
                alias: "Sensor-Piso-1",
                timestamp: "2025-11-03T14:32:05.123Z",
                telemetry: {
                  angle_x_deg: 12.34,
                  angle_y_deg: -5.67,
                  temperature_c: 23.45,
                  acceleration: {x_g: 0.012, y_g: -0.005, z_g: 1.003},
                  gyroscope: {x_dps: 0.5, y_dps: -0.3, z_dps: 0.1},
                  load_kg: 120,
                  sample_count: 45678
                },
                status: "ok"
              }
            * Encolar payload en buffer de telemetría
            * (Opcional) Publicar a MQTT
          - Si timeout/error:
            * Incrementar contador de errores
            * Si 3 fallos consecutivos: marcar device.status = "offline"
            * Encolar payload con status="error"
          - Pausa inter-frame: 50ms
        * Sleep(interval_sec - tiempo_gastado)
   c) Responder a frontend: {status: "started", polling_id: "abc123"}

3. Frontend:
   a) Cambiar botón a "Pausar Polling"
   b) Abrir WebSocket/SSE a /api/polling/stream
   c) Al recibir payload vía WebSocket:
      - Actualizar tarjeta de dispositivo con nuevos valores
      - Actualizar timestamp
      - Cambiar indicador de estado (🟢/🔴)
      - Añadir evento al log: "UnitID 2: Telemetry received"
```

---

#### 4.3.2. Actualización en Tiempo Real (WebSocket)

**Arquitectura**:
- Backend: Flask-SocketIO emite eventos `telemetry_update` cada vez que PollingService obtiene datos
- Frontend: Socket.IO client escucha eventos y actualiza DOM dinámicamente

**Evento emitido por backend**:
```javascript
socket.emit('telemetry_update', {
  unit_id: 2,
  alias: "Sensor-Piso-1",
  timestamp: "2025-11-03T14:32:05.123Z",
  telemetry: { /* datos normalizados */ },
  status: "ok"
})
```

**Frontend handling**:
```javascript
socket.on('telemetry_update', (data) => {
  const card = document.getElementById(`device-${data.unit_id}`);
  card.querySelector('.angle-x').textContent = data.telemetry.angle_x_deg.toFixed(2);
  card.querySelector('.temperature').textContent = data.telemetry.temperature_c.toFixed(2);
  // ... actualizar todos los campos
  card.querySelector('.status-indicator').className = data.status === 'ok' ? 'green' : 'red';
  card.querySelector('.timestamp').textContent = new Date(data.timestamp).toLocaleTimeString();
});
```

---

#### 4.3.3. Pausar/Detener Polling

**Trigger**: Usuario pulsa **"Pausar Polling"**.

```
1. Frontend envía POST /api/polling/stop

2. Backend:
   a) PollingService.stop() → señal para terminar bucle
   b) Thread se detiene limpiamente
   c) Responder: {status: "stopped"}

3. Frontend:
   a) Cerrar WebSocket
   b) Cambiar botón a "Iniciar Polling"
   c) Mantener últimos valores en pantalla (no borrar)
```

---

### 4.4. Gestión de Errores y Reintentos

#### 4.4.1. Timeout en Lectura Modbus

```
- Timeout: 1s por trama
- Estrategia:
  1. Si timeout → reintentar inmediatamente (1 retry)
  2. Si 2do timeout → registrar error, skip dispositivo en este ciclo
  3. Si 3 timeouts consecutivos en ciclos diferentes → marcar device.status = "offline"
  4. Continuar intentando cada ciclo (no remover de lista)
  5. Si responde de nuevo → device.status = "online", reset contador errores
```

#### 4.4.2. CRC Error

```
- Action: incrementar contador de errores CRC en stats
- No reintentar (frame corrupto, probablemente colisión en bus)
- Registrar en log: "UnitID X: CRC error"
- Frontend muestra en log de eventos
```

#### 4.4.3. Excepción Modbus

```
- Códigos comunes:
  * 0x01 (Illegal Function): firmware no soporta esa función → skip operación
  * 0x02 (Illegal Address): registro no implementado → verificar mapa
  * 0x03 (Illegal Value): validar rango antes de escribir
  * 0x04 (Device Failure): hardware error → marcar "degraded", notificar vía MQTT

- Action: registrar en log con código de excepción, mostrar en UI
```

---

## 5. Normalización de Datos

### 5.1. Conversión de Escalados

| Campo Modbus                | Registro Crudo (int16) | Escala   | Fórmula Normalización       | Unidad Real |
|-----------------------------|------------------------|----------|-----------------------------|-------------|
| `IR_MED_ANGULO_X_CDEG`      | `raw_angle_x`          | ×100     | `raw / 100.0`               | ° (grados)  |
| `IR_MED_ANGULO_Y_CDEG`      | `raw_angle_y`          | ×100     | `raw / 100.0`               | ° (grados)  |
| `IR_MED_TEMPERATURA_CENTI`  | `raw_temp`             | ×100     | `raw / 100.0`               | °C          |
| `IR_MED_ACEL_X_mG`          | `raw_acc_x`            | mg       | `raw / 1000.0`              | g           |
| `IR_MED_ACEL_Y_mG`          | `raw_acc_y`            | mg       | `raw / 1000.0`              | g           |
| `IR_MED_ACEL_Z_mG`          | `raw_acc_z`            | mg       | `raw / 1000.0`              | g           |
| `IR_MED_GIRO_X_mdps`        | `raw_gyro_x`           | mdps     | `raw / 1000.0`              | °/s         |
| `IR_MED_GIRO_Y_mdps`        | `raw_gyro_y`           | mdps     | `raw / 1000.0`              | °/s         |
| `IR_MED_GIRO_Z_mdps`        | `raw_gyro_z`           | mdps     | `raw / 1000.0`              | °/s         |
| `IR_MED_PESO_KG`            | `raw_load`             | kg (sin dec.)| `raw`                    | kg          |
| `IR_MED_MUESTRAS_*`         | `raw_lo`, `raw_hi`     | 32-bit   | `(hi << 16) | lo`          | count       |

### 5.2. Payload MQTT (Ejemplo JSON)

```json
{
  "device": {
    "unit_id": 2,
    "alias": "Sensor-Piso-1",
    "vendor": "TFM Lab",
    "product": "Inclinómetro v1",
    "hw_version": "0.3",
    "fw_version": "0.1.1"
  },
  "timestamp": "2025-11-03T14:32:05.123Z",
  "telemetry": {
    "angle_x_deg": 12.34,
    "angle_y_deg": -5.67,
    "temperature_c": 23.45,
    "acceleration": {
      "x_g": 0.012,
      "y_g": -0.005,
      "z_g": 1.003
    },
    "gyroscope": {
      "x_dps": 0.5,
      "y_dps": -0.3,
      "z_dps": 0.1
    },
    "load_kg": 120,
    "sample_count": 45678
  },
  "status": {
    "state_flags": ["OK", "MPU_READY"],
    "error_flags": []
  },
  "diagnostics": {
    "rx_frames": 1234,
    "rx_crc_errors": 2,
    "tx_frames": 1200,
    "uptime_s": 3600
  }
}
```

---

## 6. Configuración del Edge

### 6.1. Archivo `.env` (Variables de Entorno)

```bash
# Puerto serie Modbus RTU
MODBUS_PORT=/dev/ttyUSB0
MODBUS_BAUDRATE=115200
MODBUS_TIMEOUT=1.0

# Rango de UnitIDs a escanear (discovery)
DEVICE_UNIT_ID_MIN=1
DEVICE_UNIT_ID_MAX=10

# Intervalo de polling (segundos)
POLL_INTERVAL_SEC=5.0

# Pausa inter-frame (ms) para evitar colisiones RS-485
INTER_FRAME_DELAY_MS=50

# MQTT Broker
MQTT_BROKER_HOST=localhost
MQTT_BROKER_PORT=1883
MQTT_USERNAME=edge_user
MQTT_PASSWORD=edge_pass
MQTT_QOS=1
MQTT_TOPIC_PREFIX=tfm/devices

# API REST (opcional)
ENABLE_REST_API=true
REST_API_HOST=0.0.0.0
REST_API_PORT=8080

# Logging
LOG_LEVEL=INFO
LOG_FILE=edge.log
```

### 6.2. Archivo `config.yaml` (Opcional, para Maps Complejos)

```yaml
devices:
  # Lista manual de dispositivos conocidos (opcional, para evitar discovery)
  - unit_id: 2
    alias: "Sensor-Piso-1"
    description: "Inclinómetro en viga principal"
  - unit_id: 3
    alias: "Sensor-Piso-2"
    description: "Inclinómetro en viga secundaria"

modbus:
  port: "/dev/ttyUSB0"
  baudrate: 115200
  timeout: 1.0
  inter_frame_delay_ms: 50

mqtt:
  broker:
    host: "localhost"
    port: 1883
    username: "edge_user"
    password: "edge_pass"
  topics:
    telemetry: "tfm/devices/{unit_id}/telemetry"
    status: "tfm/devices/{unit_id}/status"
    edge_status: "tfm/edge/status"
  qos: 1
  retain: false

polling:
  interval_sec: 5.0
  # Prioridades de lectura (opcional, para optimizar ancho de banda)
  high_priority_regs: ["angles", "temperature"]
  low_priority_regs: ["diagnostics"]

logging:
  level: "INFO"
  file: "edge.log"
  format: "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

api:
  enabled: true
  host: "0.0.0.0"
  port: 8080
```

---

## 7. API REST (Flask Backend)

### 7.1. Rutas de Navegación (Web UI)

| Método | Ruta          | Descripción                                      |
|--------|---------------|--------------------------------------------------|
| GET    | `/`           | Dashboard principal (info adaptador, navegación) |
| GET    | `/config`     | Ventana de configuración (discovery, alias, etc.)|
| GET    | `/polling`    | Ventana de polling en vivo (telemetría)          |

---

### 7.2. Endpoints API Backend

#### **Información del Adaptador**
| Método | Ruta                   | Descripción                                      |
|--------|------------------------|--------------------------------------------------|
| GET    | `/api/adapter`         | Info del adaptador USB-RS485 (puerto, baud, estado) |

**Response:**
```json
{
  "port": "/dev/ttyUSB0",
  "baudrate": 115200,
  "status": "connected",
  "stats": {
    "total_tx_frames": 1234,
    "total_rx_frames": 1200,
    "crc_errors": 5,
    "active_devices": 3
  }
}
```

---

#### **Discovery y Gestión de Dispositivos**
| Método | Ruta                          | Descripción                                      |
|--------|-------------------------------|--------------------------------------------------|
| POST   | `/api/discover`               | Ejecutar discovery de dispositivos (rango UnitID)|
| GET    | `/api/devices`                | Lista todos los dispositivos en caché            |
| GET    | `/api/devices/{unit_id}`      | Info de un dispositivo específico                |
| POST   | `/api/devices/{unit_id}/identify` | Activar LED de identificación (blink)        |
| PUT    | `/api/devices/{unit_id}/alias`    | Actualizar alias y guardar a EEPROM          |
| PUT    | `/api/devices/{unit_id}/unit_id`  | Cambiar Unit ID y guardar a EEPROM           |

**POST `/api/discover`**  
Request:
```json
{
  "unit_id_min": 1,
  "unit_id_max": 10
}
```
Response:
```json
{
  "status": "completed",
  "devices_found": [
    {
      "unit_id": 2,
      "vendor_id": "0x5446",
      "product_id": "0x4D30",
      "hw_version": "0.3.2",
      "fw_version": "0.1.1",
      "alias": "Sensor-Piso-1",
      "capabilities": ["RS485", "MPU6050", "Identify"],
      "status": "online"
    },
    {
      "unit_id": 3,
      "vendor_id": "0x5446",
      "product_id": "0x4D30",
      "hw_version": "0.3.2",
      "fw_version": "0.1.1",
      "alias": "Sensor-Piso-2",
      "capabilities": ["RS485", "MPU6050", "Identify"],
      "status": "online"
    }
  ]
}
```

**POST `/api/devices/2/identify`**  
Request:
```json
{
  "duration_sec": 10
}
```
Response:
```json
{
  "status": "ok",
  "message": "Identify command sent to unit 2 for 10 seconds"
}
```

**PUT `/api/devices/2/alias`**  
Request:
```json
{
  "alias": "Nuevo-Alias"
}
```
Response:
```json
{
  "status": "ok",
  "message": "Alias saved to EEPROM",
  "device": {
    "unit_id": 2,
    "alias": "Nuevo-Alias"
  }
}
```

---

#### **Polling y Telemetría en Tiempo Real**
| Método | Ruta                          | Descripción                                      |
|--------|-------------------------------|--------------------------------------------------|
| POST   | `/api/polling/start`          | Iniciar polling automático                       |
| POST   | `/api/polling/stop`           | Detener polling automático                       |
| GET    | `/api/polling/status`         | Estado actual del polling (activo/inactivo)      |
| GET    | `/api/polling/stream`         | WebSocket/SSE para stream de telemetría          |
| GET    | `/api/devices/{unit_id}/telemetry` | Última telemetría leída (snapshot)         |

**POST `/api/polling/start`**  
Request:
```json
{
  "interval_sec": 5.0,
  "unit_ids": [2, 3]
}
```
Response:
```json
{
  "status": "started",
  "polling_id": "abc123",
  "interval_sec": 5.0,
  "devices": [2, 3]
}
```

**GET `/api/polling/status`**  
Response:
```json
{
  "active": true,
  "polling_id": "abc123",
  "interval_sec": 5.0,
  "devices": [2, 3],
  "uptime_sec": 120
}
```

**WebSocket `/api/polling/stream`** (Socket.IO)  
Events emitted:
- `telemetry_update`: payload con telemetría de un dispositivo
- `device_offline`: cuando dispositivo deja de responder
- `device_online`: cuando dispositivo vuelve a responder

Example event:
```json
{
  "event": "telemetry_update",
  "data": {
    "unit_id": 2,
    "alias": "Sensor-Piso-1",
    "timestamp": "2025-11-03T14:32:05.123Z",
    "telemetry": {
      "angle_x_deg": 12.34,
      "angle_y_deg": -5.67,
      "temperature_c": 23.45,
      "acceleration": {"x_g": 0.012, "y_g": -0.005, "z_g": 1.003},
      "gyroscope": {"x_dps": 0.5, "y_dps": -0.3, "z_dps": 0.1},
      "load_kg": 120,
      "sample_count": 45678
    },
    "status": "ok"
  }
}
```

---

#### **Health y Diagnóstico**
| Método | Ruta           | Descripción                                      |
|--------|----------------|--------------------------------------------------|
| GET    | `/api/health`  | Estado del Edge (uptime, conexión MQTT, etc.)    |

**GET `/api/health`**  
Response:
```json
{
  "status": "healthy",
  "uptime_sec": 3600,
  "modbus": {
    "connected": true,
    "port": "/dev/ttyUSB0"
  },
  "mqtt": {
    "connected": false,
    "broker": "localhost:1883"
  },
  "polling": {
    "active": true,
    "devices_monitored": 2
  }
}
```

---

## 8. Interfaz de Usuario (UI/UX)

### 8.1. Dashboard Principal (Home)

**URL**: `/`

**Layout**:
```
┌──────────────────────────────────────────────────────────┐
│  TFM Supervisor de Cargas - Dashboard                    │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  📡 Adaptador USB-RS485                                  │
│  ┌────────────────────────────────────────────────────┐ │
│  │ Puerto:      /dev/ttyUSB0                          │ │
│  │ Baudrate:    115200 bps                            │ │
│  │ Estado:      🟢 Conectado                          │ │
│  │                                                    │ │
│  │ Estadísticas Globales:                             │ │
│  │  - Tramas TX:        1234                          │ │
│  │  - Tramas RX:        1200                          │ │
│  │  - Errores CRC:      5                             │ │
│  │  - Dispositivos:     3 activos                     │ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
│  Navegación:                                             │
│  ┌──────────────────┐  ┌──────────────────┐            │
│  │  🔧 Configuración │  │  📊 Polling Vivo │            │
│  └──────────────────┘  └──────────────────┘            │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

**Elementos**:
- Header: Título del sistema
- Panel de info del adaptador: puerto, baudrate, estado (🟢/🔴)
- Estadísticas globales: contadores de tramas, errores, dispositivos activos
- 2 botones grandes de navegación:
  - 🔧 **Configuración** → `/config`
  - 📊 **Polling en Vivo** → `/polling`

---

### 8.2. Ventana de Configuración

**URL**: `/config`

**Layout**:
```
┌──────────────────────────────────────────────────────────┐
│  ⬅️ Volver | Configuración de Dispositivos              │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  🔍 Discovery de Red                                     │
│  ┌────────────────────────────────────────────────────┐ │
│  │ Rango UnitID:  [1] a [10]  [Escanear Red]         │ │
│  │ Estado: Listo para escanear                        │ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
│  📋 Dispositivos Encontrados                             │
│  ┌────────────────────────────────────────────────────┐ │
│  │ UnitID │ Vendor │ Product │ HW │ FW │ Alias │ 🔦 💾│ │
│  ├────────┼────────┼─────────┼────┼────┼───────┼──────┤ │
│  │   2    │ TFM Lab│ Inclin. │0.3 │0.1 │[Sensor]│🔦 💾│ │
│  │   3    │ TFM Lab│ Inclin. │0.3 │0.1 │[Piso-2]│🔦 💾│ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
│  * Alias: Click para editar inline                      │
│  * 🔦: Identify (parpadea LED)                           │
│  * 💾: Guardar alias a EEPROM                            │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

**Elementos**:
1. **Botón Volver**: Regresa a Dashboard
2. **Panel de Discovery**:
   - Input: rango de UnitIDs (min, max)
   - Botón: **"Escanear Red"** → activa discovery
   - Barra de progreso durante escaneo
   - Mensaje de estado: "Escaneando UnitID 5/10..." → "Completado: 3 dispositivos encontrados"
3. **Tabla de Dispositivos**:
   - Columnas: UnitID, Vendor, Product, HW, FW, Alias (editable), Acciones
   - Alias: input text inline, editable
   - Acciones:
     - 🔦 **Identify**: botón → modal de confirmación → parpadea LED
     - 💾 **Guardar**: botón → guarda alias a EEPROM vía 0x10 + 0xA55A
     - (Opcional) 🔄 **Cambiar UnitID**: modal con input de nuevo UnitID

**Interacciones**:
- Usuario edita alias en input → pulsa 💾 → backend ejecuta 0x10 + 0xA55A → notificación "Alias guardado"
- Usuario pulsa 🔦 → modal "¿Identificar dispositivo por X segundos?" → backend ejecuta 0x06 a HR_CMD_IDENT → LED parpadea
- Discovery en progreso: deshabilitar botón "Escanear Red", mostrar spinner

---

### 8.3. Ventana de Polling (Live Telemetry)

**URL**: `/polling`

**Layout**:
```
┌──────────────────────────────────────────────────────────┐
│  ⬅️ Volver | Polling en Tiempo Real                      │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  🎛️ Controles de Polling                                 │
│  ┌────────────────────────────────────────────────────┐ │
│  │ Intervalo: [5] segundos                            │ │
│  │ Dispositivos: ☑️ UnitID 2  ☑️ UnitID 3  ☐ UnitID 4 │ │
│  │ [▶️ Iniciar Polling]  Estado: Detenido             │ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
│  📊 Telemetría en Vivo                                   │
│  ┌────────────────────┐  ┌────────────────────┐        │
│  │ UnitID 2           │  │ UnitID 3           │        │
│  │ Sensor-Piso-1      │  │ Sensor-Piso-2      │        │
│  │ 🟢 14:32:05        │  │ 🟢 14:32:05        │        │
│  ├────────────────────┤  ├────────────────────┤        │
│  │ 📐 Ángulo X: 12.3° │  │ 📐 Ángulo X: -5.2° │        │
│  │ 📐 Ángulo Y: -5.6° │  │ 📐 Ángulo Y: 3.1°  │        │
│  │ 🌡️ Temp: 23.4 °C   │  │ 🌡️ Temp: 22.8 °C   │        │
│  │ 📈 Acel X: 0.012g  │  │ 📈 Acel X: -0.005g │        │
│  │ 📈 Acel Y: -0.005g │  │ 📈 Acel Y: 0.002g  │        │
│  │ 📈 Acel Z: 1.003g  │  │ 📈 Acel Z: 0.998g  │        │
│  │ 🔄 Gyro X: 0.5°/s  │  │ 🔄 Gyro X: -0.2°/s │        │
│  │ 🔄 Gyro Y: -0.3°/s │  │ 🔄 Gyro Y: 0.1°/s  │        │
│  │ 🔄 Gyro Z: 0.1°/s  │  │ 🔄 Gyro Z: 0.0°/s  │        │
│  │ ⚖️ Peso: 120 kg    │  │ ⚖️ Peso: 85 kg     │        │
│  │ 🔢 Muestras: 45678 │  │ 🔢 Muestras: 34567 │        │
│  └────────────────────┘  └────────────────────┘        │
│                                                          │
│  📝 Log de Eventos (últimos 10)                          │
│  ┌────────────────────────────────────────────────────┐ │
│  │ 14:32:05 - UnitID 2: Telemetría recibida          │ │
│  │ 14:32:05 - UnitID 3: Telemetría recibida          │ │
│  │ 14:32:00 - UnitID 2: Telemetría recibida          │ │
│  │ 14:31:58 - UnitID 3: Timeout (reintentando...)    │ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

**Elementos**:
1. **Botón Volver**: Regresa a Dashboard
2. **Panel de Controles**:
   - Input: Intervalo de polling (segundos)
   - Checkboxes: Selección múltiple de UnitIDs a monitorear
   - Botón: **"▶️ Iniciar Polling"** / **"⏸️ Pausar Polling"** (toggle)
   - Indicador de estado: "Activo" (verde) / "Detenido" (gris)
3. **Grid de Tarjetas de Telemetría** (responsive, 2-3 columnas):
   - Header: UnitID, Alias, Timestamp, Estado (🟢/🔴)
   - Body: Valores actuales con iconos (ángulo, temp, acel, gyro, peso, muestras)
   - Footer: (opcional) mini-gráfico de últimos 30s
4. **Log de Eventos**:
   - Scroll list con últimos 10-50 eventos
   - Auto-scroll al agregar nuevos
   - Formato: `HH:MM:SS - UnitID X: Mensaje`

**Interacciones**:
- Usuario marca checkboxes → pulsa "Iniciar" → backend inicia PollingService → frontend abre WebSocket
- WebSocket recibe `telemetry_update` → actualiza tarjeta correspondiente (smooth transition, fade-in de nuevos valores)
- Si dispositivo no responde 3 veces → tarjeta cambia a 🔴 y mensaje "Offline"
- Botón "Pausar" → cierra WebSocket, detiene backend PollingService → valores quedan congelados en última lectura

---

### 8.4. Estilos y UX

**Framework CSS**: Bootstrap 5 o Tailwind CSS (responsive, mobile-first)

**Colores**:
- Verde: 🟢 Online, OK
- Rojo: 🔴 Offline, Error
- Amarillo: 🟡 Degraded, Warning
- Azul: Info, Links
- Gris: Disabled, Detenido

**Animaciones**:
- Fade-in al actualizar valores de telemetría
- Spinner durante discovery
- Pulse en botón Identify durante parpadeo LED
- Highlight en tabla cuando se guarda alias

**Accesibilidad**:
- Labels claros en inputs
- Tooltips en iconos (hover)
- Keyboard navigation (Tab, Enter)
- ARIA labels para screen readers

## 9. Manejo de Errores y Reintentos

### 9.1. Estrategia de Timeouts
- **Reintento inmediato**: Si timeout/excepción, reintentar 1 vez con backoff de 100ms.
- **Skip dispositivo**: Si 3 fallos consecutivos, marcar como "offline" temporalmente.
- **Re-scan periódico**: Cada 5 min, intentar leer dispositivos "offline" para detectar si volvieron.

### 9.2. Excepciones Modbus

| Código | Nombre                     | Acción del Edge                                          |
|--------|----------------------------|----------------------------------------------------------|
| 0x01   | Illegal Function           | Registrar error; no reintentar esa función               |
| 0x02   | Illegal Data Address       | Validar mapa de registros; posible incompatibilidad FW   |
| 0x03   | Illegal Data Value         | Validar rangos antes de escribir                         |
| 0x04   | Server Device Failure      | Marcar dispositivo como "degraded"; notificar vía MQTT   |

### 9.3. Logging

```python
# Ejemplo de log estructurado
log.info("Device discovered", extra={
    "unit_id": 2,
    "alias": "Sensor-Piso-1",
    "hw_version": "0.3.2"
})

log.error("Modbus timeout", extra={
    "unit_id": 2,
    "function": "read_input_registers",
    "address": 0x0000,
    "count": 13,
    "retry_count": 2
})
```

---

## 10. Seguridad y Buenas Prácticas

### 10.1. Credenciales
- **No hardcodear** credenciales MQTT en código fuente.
- Usar `.env` y **nunca** commitear al repo (añadir a `.gitignore`).
- Considerar `docker secrets` o `vault` en producción.

### 10.2. Validación de Datos
- **Rango de Unit ID**: 1..247.
- **Alias**: longitud 0..64, solo ASCII imprimible.
- **Valores de sensores**: validar rangos físicos razonables (ej. ángulo ±90°).

### 10.3. Performance
- **No saturar bus RS-485**: respetar pausa inter-frame (50-100ms).
- **Polling adaptativo**: reducir frecuencia si dispositivos no responden.
- **Buffer MQTT**: si broker caído, buffear mensajes localmente (limite de memoria).

---

## 11. Testing

### 11.1. Unit Tests
- Mock de `ModbusSerialClient` para probar lógica sin hardware.
- Tests de normalización de datos (conversión de escalados).
- Tests de empaquetado/desempaquetado de alias ASCII.

### 11.2. Integration Tests
- Conectar a simulador Modbus (pymodbus server).
- Verificar lectura/escritura end-to-end.
- Probar timeouts, excepciones, re-discovery.

### 11.3. Acceptance Tests
- Edge conectado a Arduino real.
- Publicación a broker MQTT local (Mosquitto).
- Validar formato JSON en tópicos MQTT.

---

## 12. Roadmap y Extensiones Futuras

### 12.1. Fase 1 (MVP)
- [ ] Modbus RTU client básico (pymodbus)
- [ ] DeviceManager con discovery por rango UnitID
- [ ] Normalización de datos (escalados → unidades físicas)
- [ ] Flask app con 3 ventanas (Dashboard, Config, Polling)
- [ ] WebSocket/SSE para telemetría en tiempo real
- [ ] API REST completa (adapter, discover, identify, alias, unit_id, polling)
- [ ] Logging estructurado (file + console)
- [ ] UI responsive con Bootstrap 5

### 12.2. Fase 2 (Integración FIWARE)
- [ ] Context Broker (Orion) via NGSI-v2
- [ ] IoT Agent Modbus (alternativa)
- [ ] Persistencia en QuantumLeap (históricos)
- [ ] MQTT Publisher (opcional, paralelo a FIWARE)

### 12.3. Fase 3 (Avanzado)
- [ ] Gráficos en tiempo real (Chart.js/Plotly) en ventana de polling
- [ ] Dashboard con métricas agregadas (promedio, min, max por dispositivo)
- [ ] Alertas por umbrales (temp > 50°C, ángulo > 30°) → notificaciones push
- [ ] OTA firmware update via Edge (upload .hex, bootloader protocol)
- [ ] Multi-usuario con autenticación (Flask-Login, roles admin/viewer)
- [ ] Exportación de datos históricos (CSV, JSON)

---

## 13. Referencias

- **Modbus RTU Specification**: https://modbus.org/docs/Modbus_over_serial_line_V1_02.pdf
- **MQTT Protocol**: https://mqtt.org/mqtt-specification/
- **FIWARE IoT Agent**: https://fiware-iotagent-node-lib.readthedocs.io/
- **pymodbus Documentation**: https://pymodbus.readthedocs.io/
- **Flask Documentation**: https://flask.palletsprojects.com/
- **Flask-SocketIO**: https://flask-socketio.readthedocs.io/
- **Bootstrap 5**: https://getbootstrap.com/docs/5.0/

---

## 14. Aprobación

Este documento define la **arquitectura de 3 ventanas** (Dashboard, Configuración, Polling) para el Edge Layer del sistema TFM Supervisor de Cargas.

**Cambios clave respecto a versión anterior**:
- ✅ Separación clara: **Configuración** (discovery, alias, identify) vs **Polling** (telemetría en vivo)
- ✅ Dashboard principal con info del adaptador y navegación
- ✅ WebSocket para actualización en tiempo real de telemetría
- ✅ UI detallada con mockups de layout, elementos, interacciones
- ✅ API REST completa para todas las operaciones

**Estado**: 🟢 Listo para implementación  
**Autor**: Copilot + Sergio Lobo  
**Fecha**: 2025-11-03  
**Versión**: 2.0 (Arquitectura 3 Ventanas)
