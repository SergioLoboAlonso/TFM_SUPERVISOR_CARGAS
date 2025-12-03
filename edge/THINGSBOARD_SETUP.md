# Guía de Integración con ThingsBoard

Esta guía explica cómo conectar el Edge Layer al servidor ThingsBoard para visualización y análisis de telemetría.

## Opciones de Despliegue

### Opción 1: ThingsBoard Cloud (Demo Server) - **Recomendado para empezar**

**Ventajas:**
- No requiere instalación
- Gratis para pruebas
- Disponible inmediatamente

**URL:** https://demo.thingsboard.io

### Opción 2: ThingsBoard Local (Docker)

**Ventajas:**
- Control total
- Sin límites de dispositivos
- Datos en local

---

## PASO 1: Configurar ThingsBoard Cloud

### 1.1 Crear Cuenta

1. Ir a https://demo.thingsboard.io
2. Click en **"Sign Up"**
3. Crear cuenta con email y contraseña
4. Verificar email

### 1.2 Login

1. Ir a https://demo.thingsboard.io/login
2. Ingresar credenciales
3. Click **"Login"**

---

## PASO 2: Crear Dispositivos

### 2.1 Crear Dispositivo Unit 1 (WindMeter)

1. En el menú lateral: **Devices** → **+ (Add Device)**
2. Configurar:
   - **Name:** `WindMeter_Unit1`
   - **Device Profile:** `default`
   - **Label:** `Wind Sensor`
3. Click **"Add"**

### 2.2 Obtener Access Token

1. Click en el dispositivo `WindMeter_Unit1`
2. Click pestaña **"Details"**
3. Copiar **"Access Token"** (ejemplo: `A1_TEST_TOKEN`)
4. Guardar este token

### 2.3 Crear Dispositivo Unit 2 (PA_L)

1. **Devices** → **+ (Add Device)**
2. Configurar:
   - **Name:** `PA_L_Unit2`
   - **Device Profile:** `default`
   - **Label:** `Tilt & Wind Sensor`
3. Click **"Add"**
4. Copiar **Access Token** del dispositivo

---

## PASO 3: Configurar Edge Service

### 3.1 Editar .env

```bash
cd /home/edge_sergio/Desktop/TFM_SUPERVISOR_CARGAS/edge
nano .env
```

### 3.2 Configuración MQTT para ThingsBoard

**Para Unit 1 (WindMeter):**
```bash
# ThingsBoard MQTT Configuration
MQTT_BROKER_HOST=demo.thingsboard.io
MQTT_BROKER_PORT=1883
MQTT_USERNAME=A1_TEST_TOKEN          # Reemplazar con tu Access Token
MQTT_PASSWORD=
MQTT_QOS=1
MQTT_TOPIC_PREFIX=v1/devices/me      # Topic de ThingsBoard
```

> ⚠️ **PROBLEMA:** El Edge Service actual solo soporta UN broker MQTT, pero tienes 2 dispositivos con tokens diferentes.

### 3.3 Soluciones

#### **Solución A: Gateway Device (Recomendado)**

Crear UN SOLO dispositivo gateway en ThingsBoard que represente el Edge completo:

1. **Devices** → **+ (Add Device)**
2. Configurar:
   - **Name:** `Edge_Gateway`
   - **Device Profile:** `default`
   - **Label:** `Edge Supervisor Gateway`
3. Copiar Access Token

4. Editar `.env`:
```bash
MQTT_BROKER_HOST=demo.thingsboard.io
MQTT_BROKER_PORT=1883
MQTT_USERNAME=<GATEWAY_ACCESS_TOKEN>
MQTT_PASSWORD=
MQTT_QOS=1
MQTT_TOPIC_PREFIX=v1/gateway
```

5. El Edge publicará telemetría de TODOS los dispositivos bajo este gateway.

#### **Solución B: Modificar Código para Multi-Device**

Modificar `mqtt_bridge.py` para usar diferentes tokens según device_id (requiere desarrollo adicional).

---

## PASO 4: Adaptar Topics para ThingsBoard

ThingsBoard usa una estructura de topics diferente:

### 4.1 Topics de ThingsBoard

**Publicar telemetría:**
```
v1/devices/me/telemetry
```

**Payload:**
```json
{
  "temperature": 18.85,
  "tilt_x": -0.46,
  "tilt_y": -1.43,
  "wind_speed": 18.22
}
```

### 4.2 Modificar mqtt_bridge.py

Necesitas adaptar el método `publish_measurement()` para formato ThingsBoard:

**Ubicación:** `/home/edge_sergio/Desktop/TFM_SUPERVISOR_CARGAS/edge/src/mqtt_bridge.py`

**Cambio necesario:**

```python
def publish_measurement_thingsboard(self, measurements_dict):
    """
    Publica medidas en formato ThingsBoard.
    
    Args:
        measurements_dict: Dict con múltiples medidas
                          {"temperature": 18.5, "tilt_x": -0.5, ...}
    """
    topic = "v1/devices/me/telemetry"
    payload = json.dumps(measurements_dict)
    
    result = self.client.publish(topic, payload, qos=self.qos)
    return result.rc == mqtt.MQTT_ERR_SUCCESS
```

---

## PASO 5: Reiniciar Servicio

```bash
# Reiniciar Edge Service
sudo systemctl restart tfm-edge.service

# Verificar conexión
journalctl -u tfm-edge.service -f | grep -i mqtt
```

Deberías ver:
```
✅ Conectado a broker MQTT demo.thingsboard.io:1883
```

---

## PASO 6: Verificar Datos en ThingsBoard

### 6.1 Ver Telemetría en Tiempo Real

1. Ir a **Devices** → Click en `Edge_Gateway`
2. Click pestaña **"Latest Telemetry"**
3. Deberías ver datos llegando en tiempo real:
   - `temperature`
   - `tilt_x`
   - `tilt_y`
   - `wind_speed`

### 6.2 Si NO llegan datos

**Debug en Edge:**
```bash
# Ver logs de publicación MQTT
journalctl -u tfm-edge.service -f | grep "publicada"

# Verificar conexión
curl http://localhost:8080/api/alerts/stats
```

**Debug con mosquitto_sub:**
```bash
# Suscribirse al topic de ThingsBoard
mosquitto_sub -h demo.thingsboard.io -p 1883 \
  -u <ACCESS_TOKEN> \
  -t "v1/devices/me/telemetry" -v
```

---

## PASO 7: Crear Dashboard

### 7.1 Crear Dashboard

1. Menú lateral: **Dashboards** → **+ (Add Dashboard)**
2. Nombre: `Edge Supervisor Dashboard`
3. Click **"Add"**

### 7.2 Agregar Widgets

#### Widget 1: Gráfico de Inclinación (Tilt)

1. Click **"+ (Add widget)"**
2. Tipo: **Charts** → **Timeseries Line Chart**
3. Configurar:
   - **Datasource:** `Edge_Gateway`
   - **Timeseries keys:** `tilt_x`, `tilt_y`
   - **Label:** `Inclinación (deg)`
4. Click **"Add"**

#### Widget 2: Velocidad del Viento

1. **+ (Add widget)** → **Charts** → **Timeseries Line Chart**
2. Configurar:
   - **Datasource:** `Edge_Gateway`
   - **Timeseries keys:** `wind_speed`
   - **Label:** `Velocidad Viento (m/s)`
3. Click **"Add"**

#### Widget 3: Temperatura

1. **+ (Add widget)** → **Gauges** → **Digital Gauge**
2. Configurar:
   - **Datasource:** `Edge_Gateway`
   - **Timeseries key:** `temperature`
   - **Units:** `°C`
   - **Min/Max:** `0 / 50`
3. Click **"Add"**

#### Widget 4: Últimos Valores

1. **+ (Add widget)** → **Cards** → **Entities Table**
2. Configurar:
   - **Datasource:** `Edge_Gateway`
   - Seleccionar todas las keys
3. Click **"Add"**

### 7.3 Guardar Dashboard

Click **"✓ (Save)"** en la esquina superior derecha

---

## PASO 8: Configurar Alarmas (Opcional)

### 8.1 Crear Rule Chain para Alertas

1. **Rule Chains** → **+ (Add Rule Chain)**
2. Nombre: `Edge Alerts`
3. Agregar nodos:
   - **Message Type Switch** → Filtrar por `Post telemetry`
   - **Script Filter** → Detectar umbrales:
   ```javascript
   return msg.tilt_x > 5 || msg.tilt_x < -5;
   ```
   - **Create Alarm** → Generar alarma si umbral excedido

### 8.2 Configurar Notificaciones

1. **Notification Rules**
2. Configurar email/SMS cuando se genere alarma

---

## PASO 9: ThingsBoard Local (Alternativa Docker)

### 9.1 Instalar Docker

```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose
sudo systemctl start docker
sudo systemctl enable docker
```

### 9.2 Desplegar ThingsBoard

```bash
cd /home/edge_sergio/Desktop/TFM_SUPERVISOR_CARGAS/infra

# Crear docker-compose.yml para ThingsBoard
cat > docker-compose-thingsboard.yml <<EOF
version: '3.8'

services:
  thingsboard:
    image: thingsboard/tb-postgres
    container_name: thingsboard
    restart: unless-stopped
    ports:
      - "9090:9090"   # HTTP UI
      - "1883:1883"   # MQTT
      - "5683:5683"   # CoAP
    environment:
      TB_QUEUE_TYPE: in-memory
    volumes:
      - tb-data:/data
      - tb-logs:/var/log/thingsboard

volumes:
  tb-data:
  tb-logs:
EOF

# Iniciar ThingsBoard
docker-compose -f docker-compose-thingsboard.yml up -d

# Ver logs
docker logs -f thingsboard
```

### 9.3 Acceder a ThingsBoard Local

1. URL: http://localhost:9090
2. Credenciales por defecto:
   - **Usuario:** `tenant@thingsboard.org`
   - **Password:** `tenant`

3. Configurar Edge Service para localhost:
```bash
MQTT_BROKER_HOST=localhost
MQTT_BROKER_PORT=1883
```

---

## Troubleshooting

### Error: "Connection Refused"

**Causa:** ThingsBoard no acepta la conexión

**Solución:**
```bash
# Verificar firewall
sudo ufw allow 1883/tcp

# Ping al servidor
ping demo.thingsboard.io

# Verificar token
echo "Token: $MQTT_USERNAME"
```

### Error: "No Data in ThingsBoard"

**Causa:** Topics o payload incorrectos

**Solución:**
```bash
# Verificar logs de Edge
journalctl -u tfm-edge.service -f | grep MQTT

# Test manual de publicación
mosquitto_pub -h demo.thingsboard.io -p 1883 \
  -u <ACCESS_TOKEN> \
  -t "v1/devices/me/telemetry" \
  -m '{"test": 123}'
```

### Error: "Invalid Access Token"

**Causa:** Token incorrecto o dispositivo eliminado

**Solución:**
1. Verificar dispositivo existe en ThingsBoard
2. Copiar nuevo Access Token
3. Actualizar `.env`
4. Reiniciar servicio

---

## Próximos Pasos

- [ ] Crear Rule Chains para procesamiento de datos
- [ ] Configurar alertas por email/SMS
- [ ] Integrar con APIs REST de ThingsBoard
- [ ] Exportar datos históricos
- [ ] Configurar usuarios y permisos

---

## Referencias

- **ThingsBoard Docs:** https://thingsboard.io/docs/
- **MQTT API:** https://thingsboard.io/docs/reference/mqtt-api/
- **Gateway API:** https://thingsboard.io/docs/reference/gateway-mqtt-api/
- **Dashboards:** https://thingsboard.io/docs/user-guide/dashboards/

---

**Autor:** Sergio Lobo  
**Fecha:** 2025-12-03  
**Sistema:** Edge Layer - TFM Supervisor de Cargas
