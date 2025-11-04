# Edge Layer - Inicio Rápido

## 🚀 Instalación y Primer Arranque

### 1. Preparar entorno Python

```bash
cd edge/
python3 -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configurar puerto RS-485

```bash
# Copiar plantilla de configuración
cp .env.example .env

# Identificar tu adaptador RS-485
ls -l /dev/tty.usb*

# Editar .env con tu puerto correcto
nano .env
# Cambiar: MODBUS_PORT=/dev/tty.usbmodem5A300455411  (← TU PUERTO AQUÍ)
```

### 3. Iniciar el servidor

```bash
# Opción A: Script de arranque
./start_edge.sh

# Opción B: Python directo
python3 -m src.app
```

### 4. Abrir interfaz web

Abre tu navegador en: **http://localhost:8080**

---

## 🖥️ Uso de la Interfaz

### Dashboard (/)
- Ver estado del adaptador USB-RS485
- Estadísticas globales (TX/RX, errores, dispositivos activos)
- Navegación a Config y Polling

### Configuración (/config)
- **Discovery**: Escanear red Modbus RTU (rango de UnitID 1-150)
- **Gestionar dispositivos**: Ver vendor/product, versiones HW/FW
- **Alias**: Editar alias y guardar en EEPROM (0x0030-0x004F)
- **Identify**: Parpadear LED del dispositivo por 10s (comando 0x0013)

### Polling (/polling)
- **Seleccionar dispositivos**: Multi-selección con Ctrl/Cmd
- **Configurar intervalo**: 0.1-60 segundos (default 1.0s)
- **Monitoreo en tiempo real**: Telemetría vía WebSocket
  - Ángulos X/Y (°)
  - Temperatura (°C)
  - Aceleración X/Y/Z (g)
  - Giroscopio X/Y/Z (°/s)
  - Carga (kg)
  - Sample counter

---

## 🔧 Solución de Problemas

### Error: "MODBUS_PORT no configurado"
```bash
# Asegúrate de que .env existe y tiene MODBUS_PORT configurado
cat .env | grep MODBUS_PORT
```

### Error: "No se pudo conectar al puerto"
```bash
# Verifica que el puerto existe
ls -l /dev/tty.usb*

# Verifica permisos
ls -l /dev/tty.usbmodem5A300455411

# En Linux, agregar usuario al grupo dialout
sudo usermod -a -G dialout $USER
# Luego cerrar sesión y volver a entrar
```

### Discovery no encuentra dispositivos
- Verifica que los dispositivos estén encendidos
- Confirma conexión RS-485 (A/B, GND)
- Amplía el rango: `DEVICE_UNIT_ID_MIN=1, MAX=247` en .env
- Revisa baudrate (debe coincidir con firmware: 115200)

### WebSocket no conecta
- Verifica que el servidor esté corriendo
- Revisa firewall (puerto 8080)
- Mira la consola del navegador (F12)

---

## 📂 Estructura del Proyecto

```
edge/
├── .env                     # Configuración (NO commitear)
├── .env.example             # Plantilla de configuración
├── requirements.txt         # Dependencias Python
├── start_edge.sh            # Script de arranque
├── README.md                # Este archivo
├── src/
│   ├── __init__.py
│   ├── app.py               # Flask app + API REST + WebSocket
│   ├── config.py            # Carga de configuración
│   ├── logger.py            # Logging estructurado
│   ├── modbus_client.py     # Wrapper pymodbus con retry
│   ├── device_manager.py    # Discovery, identify, alias, UnitID
│   ├── data_normalizer.py   # Conversión Modbus → unidades físicas
│   └── polling_service.py   # Polling automático con thread
├── templates/
│   ├── dashboard.html       # Vista principal
│   ├── config.html          # Configuración dispositivos
│   └── polling.html         # Telemetría en vivo
├── static/
│   ├── css/
│   │   └── style.css        # Estilos personalizados
│   └── js/
│       ├── dashboard.js     # Lógica dashboard
│       ├── config.js        # Lógica config (discovery, alias)
│       └── polling.js       # WebSocket + telemetría
└── tests/
    └── ...                  # Tests unitarios (por implementar)
```

---

## 🔗 API REST

### Adaptador
- `GET /api/adapter` → Info del adaptador USB-RS485
- `GET /api/health` → Health check

### Dispositivos
- `POST /api/discover` → Discovery de dispositivos
- `GET /api/devices` → Lista dispositivos en caché
- `GET /api/devices/{unit_id}` → Info de un dispositivo
- `POST /api/devices/{unit_id}/identify` → Parpadear LED
- `PUT /api/devices/{unit_id}/alias` → Guardar alias a EEPROM
- `PUT /api/devices/{unit_id}/unit_id` → Cambiar UnitID

### Polling
- `POST /api/polling/start` → Iniciar polling automático
- `POST /api/polling/stop` → Detener polling
- `GET /api/polling/status` → Estado del polling

### WebSocket
- `ws://localhost:8080/socket.io/` → Eventos en tiempo real
  - `telemetry_update`: Datos de telemetría
  - `device_offline`: Dispositivo perdió conexión

---

## 📋 Logs

```bash
# Ver logs en tiempo real
tail -f edge.log

# Cambiar nivel de log
# En .env: LOG_LEVEL=DEBUG
```

---

## 🧪 Próximos Pasos

1. **Probar discovery**: Escanea UnitID 1-10 en /config
2. **Verificar identify**: Confirma que el LED parpadea
3. **Monitorear telemetría**: Inicia polling en /polling
4. **Integración FIWARE**: Publicar a Orion Context Broker (roadmap)
5. **Tests unitarios**: Implementar test_normalizer.py, test_device_manager.py

---

## 📚 Referencias

- [Especificación Edge Layer](../docs/edge_specification.md)
- [Modbus RTU Protocol](../docs/protocolos/modbus.md)
- [Register Map](../firmware/lib/ModbusRTU/include/registersModbus.h)
- [Flask Documentation](https://flask.palletsprojects.com/)
- [Flask-SocketIO](https://flask-socketio.readthedocs.io/)
- [pymodbus](https://pymodbus.readthedocs.io/)
