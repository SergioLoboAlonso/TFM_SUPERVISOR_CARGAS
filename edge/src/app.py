"""
============================================================================
EDGE LAYER - Aplicación Principal Flask
============================================================================

Responsabilidades:
    1. Servidor web Flask con interfaz HTML (Dashboard, Config, Polling)
    2. API REST para operaciones CRUD de dispositivos Modbus
    3. WebSocket (Socket.IO) para telemetría en tiempo real
    4. Orquestación de servicios (Modbus, DeviceManager, PollingService)
    
Arquitectura:
    Flask App → DeviceManager → ModbusMaster → Serial RS-485 → Arduino
                     ↓
              PollingService (thread) → WebSocket → Frontend
    
Autor: Sergio Lobo Alonso - TFM UNIR
Fecha: Noviembre 2025
============================================================================
"""
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
from config import Config
from logger import logger
from modbus_master import ModbusMaster
from device_manager import DeviceManager
from data_normalizer import DataNormalizer
from polling_service import PollingService
from database import Database, init_db
from alert_engine import AlertEngine
from mqtt_bridge import MQTTBridge
import threading

# Inicializar Flask
app = Flask(__name__, 
            template_folder='../templates',
            static_folder='../static')
app.config['SECRET_KEY'] = Config.SECRET_KEY

# Inicializar SocketIO con async_mode='threading' para evitar problemas con eventlet
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Instancias globales
modbus_master: ModbusMaster = None
device_manager: DeviceManager = None
polling_service: PollingService = None
database: Database = None
alert_engine: AlertEngine = None
mqtt_bridge = None  # Puente MQTT para IoT platforms

# Estado del discovery
discovery_state = {
    'active': False,
    'current': 0,
    'total': 0,
    'unit_id': 0
}

def init_modbus():
    """
    Inicializa la stack completa de comunicación Modbus RTU y servicios.
    
    Secuencia de inicialización:
        1. Database → Inicializa base de datos SQLite
        2. ModbusMaster → Abre puerto serie RS-485
        3. DeviceManager → Gestiona identidad y comandos de dispositivos
        4. AlertEngine → Motor de alertas
        5. PollingService → Thread background para telemetría continua
        6. Callbacks → Conecta eventos de polling con WebSocket
    
    Returns:
        bool: True si inicialización exitosa, False si error
    """
    global modbus_master, device_manager, polling_service, database, alert_engine, mqtt_bridge
    
    # PASO 1: Inicializar base de datos
    try:
        logger.info("Inicializando base de datos SQLite...")
        init_db()  # Crear esquema si no existe
        database = Database()
        logger.info("✅ Base de datos inicializada")
        
        # Limpieza de datos antiguos (opcional)
        deleted = database.cleanup_old_data(days=30)
        if deleted > 0:
            logger.info(f"🗑️ Limpieza inicial: {deleted} medidas antiguas eliminadas")
    except Exception as e:
        logger.error(f"Error al inicializar base de datos: {e}")
        # Continuar sin BD (degraded mode)
    
    # PASO 1.5: Inicializar MQTT Bridge
    try:
        mqtt_bridge = MQTTBridge(database)
        if mqtt_bridge.enabled:
            logger.info("✅ MQTT Bridge habilitado")
        else:
            logger.info("ℹ️  MQTT Bridge deshabilitado (no configurado)")
    except Exception as e:
        logger.error(f"Error al inicializar MQTT Bridge: {e}")
        mqtt_bridge = None
    
    # PASO 2: Determinar puerto (manual o autodetección)
    port = Config.MODBUS_PORT
    if port == 'auto':
        logger.warning("Puerto configurado como 'auto', pero autodetección deshabilitada por usuario")
        logger.warning("Configura MODBUS_PORT en .env con el puerto correcto (ej: /dev/ttyACM0)")
        return False
    
    logger.info(f"Inicializando Modbus Master en {port} @ {Config.MODBUS_BAUDRATE} baud")
    
    # PASO 3: Crear y conectar el Modbus Master (cliente serie RTU)
    modbus_master = ModbusMaster(port=port, baudrate=Config.MODBUS_BAUDRATE)
    
    if not modbus_master.connect():
        logger.error("No se pudo conectar al puerto serie. Verifica el cable y el puerto.")
        return False
    
    # PASO 4: Inicializar servicios de alto nivel
    device_manager = DeviceManager(modbus_master, DataNormalizer())
    
    # Inicializar motor de alertas con MQTT (polling_service se asignará después)
    alert_engine = AlertEngine(database, socketio, mqtt_bridge, polling_service=None)
    logger.info("✅ AlertEngine inicializado")
    
    # Polling service con alertas y MQTT integrados
    polling_service = PollingService(modbus_master, device_manager, database, alert_engine, mqtt_bridge)
    
    # Asignar polling_service al alert_engine para monitoreo de dispositivos activos
    alert_engine.polling_service = polling_service
    
    # Iniciar monitoreo de estado de dispositivos (cada 10s)
    alert_engine.start_monitoring(interval=10)
    logger.info("🔄 Monitoreo de alertas iniciado")
    
    # PASO 5: Conectar callbacks para eventos WebSocket
    polling_service.on_telemetry_callback = emit_telemetry
    polling_service.on_diagnostic_callback = emit_diagnostic
    
    logger.info("✅ Modbus Master, DeviceManager y PollingService inicializados correctamente")
    return True


def start_initial_discovery():
    """Lanza un escaneo completo de la red al arrancar en un hilo en background."""
    from config import Config as C
    global discovery_state

    if not device_manager:
        logger.warning("start_initial_discovery llamado sin device_manager inicializado")
        return

    if discovery_state['active']:
        logger.info("Discovery ya activo; omitiendo discovery inicial")
        return

    def run_discovery_startup():
        global discovery_state
        try:
            discovery_state['active'] = True
            discovery_state['total'] = C.DEVICE_UNIT_ID_MAX - C.DEVICE_UNIT_ID_MIN + 1

            def progress_callback(current, total, unit_id):
                discovery_state['current'] = current
                discovery_state['unit_id'] = unit_id
                socketio.emit('discovery_progress', {
                    'current': current,
                    'total': total,
                    'unit_id': unit_id,
                    'percentage': int((current / total) * 100)
                })

            logger.info(f"🔎 Escaneo inicial de red {C.DEVICE_UNIT_ID_MIN}..{C.DEVICE_UNIT_ID_MAX} al arrancar")
            devices = device_manager.discover_devices(C.DEVICE_UNIT_ID_MIN, C.DEVICE_UNIT_ID_MAX, progress_callback=progress_callback)
            
            # Emitir evento de finalización
            socketio.emit('discovery_complete', {
                'devices_found': len(devices),
                'devices': [d.to_dict() for d in devices]
            })
            
            # NUEVO: Registrar sensores en base de datos
            if devices and database:
                _register_sensors_to_database(devices)
            
            # NUEVO: Publicar inventario a ThingsBoard/MQTT
            if devices and mqtt_bridge:
                import time
                time.sleep(0.5)  # Breve pausa para asegurar que BD está actualizada
                _publish_sensors_inventory()
            
            # NUEVO: Iniciar polling automáticamente si se encontraron dispositivos
            if devices and polling_service:
                unit_ids = [d.unit_id for d in devices]
                logger.info(f"✅ Discovery completado: {len(devices)} dispositivos encontrados")
                logger.info(f"🔄 Iniciando polling automático para UnitIDs: {unit_ids}")
                
                # Esperar un momento para que el frontend esté listo
                import time
                time.sleep(1)
                
                # Iniciar polling con intervalo por defecto
                try:
                    polling_service.start(
                        unit_ids=unit_ids,
                        interval_sec=C.POLL_INTERVAL_SEC,
                        per_device_refresh_sec=C.PER_DEVICE_REFRESH_SEC
                    )
                    
                    # Notificar al frontend que el polling ha iniciado
                    socketio.emit('polling_auto_started', {
                        'unit_ids': unit_ids,
                        'interval_sec': C.POLL_INTERVAL_SEC,
                        'per_device_refresh_sec': C.PER_DEVICE_REFRESH_SEC
                    })
                    logger.info("✅ Polling automático iniciado correctamente")
                except Exception as e:
                    logger.error(f"❌ Error al iniciar polling automático: {e}")
                    socketio.emit('polling_auto_start_error', {'error': str(e)})
            else:
                logger.info(f"ℹ️  Discovery completado sin dispositivos; polling no iniciado")
                
        except Exception as e:
            logger.error(f"Error en discovery inicial: {e}")
            socketio.emit('discovery_error', {'error': str(e)})
        finally:
            discovery_state['active'] = False
            discovery_state['current'] = 0
            discovery_state['total'] = 0
            discovery_state['unit_id'] = 0

    t = threading.Thread(target=run_discovery_startup, daemon=True)
    t.start()


def _register_sensors_to_database(devices):
    """
    Registra dispositivos y sus sensores en la base de datos.
    
    Estrategia:
        1. Registrar el dispositivo en tabla 'devices' (unit_id, alias, capabilities, rig_id)
        2. Registrar cada sensor lógico en tabla 'sensors' (sensores individuales por capability)
        3. Configurar umbrales de alarma predeterminados según el tipo
    
    Args:
        devices: Lista de objetos Device del DeviceManager
    """
    if not database:
        logger.warning("Base de datos no disponible, dispositivos no registrados")
        return
    
    try:
        import json
        
        for device in devices:
            unit_id = device.unit_id
            alias = device.alias or f"Unit_{unit_id}"
            capabilities = list(device.capabilities) if device.capabilities else []
            
            # RIG_ID: Agrupamos por ubicación (por ahora, todos en RIG_01)
            # En producción, esto podría leerse de un archivo de configuración
            rig_id = "RIG_01"
            
            logger.info(f"📝 Registrando dispositivo {unit_id} ({alias}), caps={capabilities}")
            
            # PASO 1: Registrar el dispositivo en la tabla 'devices'
            database.upsert_device({
                'unit_id': unit_id,
                'alias': alias,
                'vendor_code': '0x4C6F',  # Código de fabricante (Lobo)
                'capabilities': json.dumps(capabilities),
                'rig_id': rig_id,
                'firmware_version': None,  # TODO: obtener de Device si está disponible
                'enabled': 1
            })
            
            # PASO 2: Registrar sensores lógicos según capabilities
            
            # CAPABILITY: MPU6050 (acelerómetro + giroscopio + temperatura)
            if 'MPU6050' in capabilities:
                # Ángulo X
                database.upsert_sensor({
                    'sensor_id': f"UNIT_{unit_id}_TILT_X",
                    'unit_id': unit_id,
                    'type': 'tilt',
                    'register': 0x0000,  # IR_MED_ANGULO_X_CDEG
                    'unit': 'deg',
                    'alarm_lo': -10.0,  # Umbral de inclinación crítica
                    'alarm_hi': 10.0,
                    'enabled': 1
                })
                
                # Ángulo Y
                database.upsert_sensor({
                    'sensor_id': f"UNIT_{unit_id}_TILT_Y",
                    'unit_id': unit_id,
                    'type': 'tilt',
                    'register': 0x0001,  # IR_MED_ANGULO_Y_CDEG
                    'unit': 'deg',
                    'alarm_lo': -10.0,
                    'alarm_hi': 10.0,
                    'enabled': 1
                })
                
                # Temperatura
                database.upsert_sensor({
                    'sensor_id': f"UNIT_{unit_id}_TEMP",
                    'unit_id': unit_id,
                    'type': 'temperature',
                    'register': 0x0002,  # IR_MED_TEMPERATURA_CENTI
                    'unit': 'celsius',
                    'alarm_lo': -10.0,  # Temperatura mínima operativa
                    'alarm_hi': 60.0,   # Temperatura máxima operativa
                    'enabled': 1
                })
                
                # Aceleración (magnitud)
                database.upsert_sensor({
                    'sensor_id': f"UNIT_{unit_id}_ACCEL",
                    'unit_id': unit_id,
                    'type': 'acceleration',
                    'register': 0x0003,  # IR_MED_ACEL_X_mG (primero del bloque)
                    'unit': 'g',
                    'alarm_lo': None,
                    'alarm_hi': 2.0,  # Alerta si aceleración > 2g
                    'enabled': 1
                })
                
                # Giroscopio (magnitud)
                database.upsert_sensor({
                    'sensor_id': f"UNIT_{unit_id}_GYRO",
                    'unit_id': unit_id,
                    'type': 'gyroscope',
                    'register': 0x0006,  # IR_MED_GIRO_X_mdps (primero del bloque)
                    'unit': 'dps',
                    'alarm_lo': None,
                    'alarm_hi': 250.0,  # Alerta si velocidad angular > 250°/s
                    'enabled': 1
                })
                
                logger.info(f"   ✅ Sensores MPU6050 registrados para unit {unit_id}")
            
            # CAPABILITY: Wind (anemómetro)
            if 'Wind' in capabilities:
                # Velocidad de viento
                database.upsert_sensor({
                    'sensor_id': f"UNIT_{unit_id}_WIND_SPEED",
                    'unit_id': unit_id,
                    'type': 'wind',
                    'register': 0x000D,  # IR_MED_VIENTO_VELOCIDAD
                    'unit': 'm/s',
                    'alarm_lo': None,
                    'alarm_hi': 25.0,  # Alerta si viento > 25 m/s (~90 km/h)
                    'enabled': 1
                })
                
                # Dirección de viento
                database.upsert_sensor({
                    'sensor_id': f"UNIT_{unit_id}_WIND_DIR",
                    'unit_id': unit_id,
                    'type': 'wind',
                    'register': 0x000E,  # IR_MED_VIENTO_DIRECCION
                    'unit': 'deg',
                    'alarm_lo': None,
                    'alarm_hi': None,  # La dirección no tiene umbrales críticos
                    'enabled': 1
                })
                
                logger.info(f"   ✅ Sensores Wind registrados para unit {unit_id}")
            
            # CAPABILITY: Load (celda de carga HX711)
            if 'Load' in capabilities:
                database.upsert_sensor({
                    'sensor_id': f"UNIT_{unit_id}_LOAD",
                    'unit_id': unit_id,
                    'type': 'load',
                    'register': 0x000C,  # IR_MED_PESO_KG
                    'unit': 'kg',
                    'alarm_lo': -5.0,   # Carga negativa anómala
                    'alarm_hi': 500.0,  # Sobrecarga
                    'enabled': 1
                })
                
                logger.info(f"   ✅ Sensor Load registrado para unit {unit_id}")
        
        logger.info(f"✅ Total de {len(devices)} dispositivos registrados en BD")
        
        # Estadísticas de sensores
        stats = database.get_db_stats()
        logger.info(f"📊 Dispositivos en BD: {stats.get('device_count', 'N/A')}")
        logger.info(f"📊 Sensores en BD: {stats['sensor_count']}")
        
    except Exception as e:
        logger.error(f"Error al registrar sensores en BD: {e}")


def emit_telemetry(telemetry_data: dict):
    """Emite telemetría vía WebSocket (desde thread background)"""
    with app.app_context():
        socketio.emit('telemetry_update', telemetry_data, namespace='/')
    logger.info(f"📡 WebSocket emit: telemetry_update para unit {telemetry_data.get('unit_id')}, status={telemetry_data.get('status')}")


def emit_diagnostic(diagnostic_data: dict):
    """Emite diagnósticos vía WebSocket (desde thread background)"""
    with app.app_context():
        socketio.emit('diagnostic_update', diagnostic_data, namespace='/')
    logger.debug(f"🔍 WebSocket emit: diagnostic_update para unit {diagnostic_data.get('unit_id')}")


def _publish_sensors_inventory():
    """
    Publica inventario completo de dispositivos y sensores a ThingsBoard.
    
    Esto permite que los dashboards se actualicen automáticamente cuando:
    - Se descubren nuevos dispositivos
    - Dispositivos cambian estado online/offline
    - Se modifican configuraciones
    """
    if not mqtt_bridge or not database:
        return
    
    try:
        # Obtener todos los dispositivos de la BD
        devices_data = database.get_all_devices(enabled_only=False)
        
        # Construir información enriquecida
        devices_info = []
        
        for dev_data in devices_data:
            unit_id = dev_data['unit_id']
            
            # Obtener lista de sensores para este dispositivo
            sensors = database.get_sensors_by_device(unit_id)
            sensor_ids = [s['sensor_id'] for s in sensors] if sensors else []
            
            # Determinar estado online (desde polling_service si está disponible)
            online = False
            if polling_service and hasattr(polling_service, '_device_online_state'):
                online = polling_service._device_online_state.get(unit_id, False)
            
            devices_info.append({
                'unit_id': unit_id,
                'alias': dev_data.get('alias', f"Unit_{unit_id}"),
                'capabilities': dev_data.get('capabilities', []),
                'enabled': dev_data.get('enabled', True),
                'online': online,
                'sensors': sensor_ids
            })
        
        # Publicar inventario a MQTT
        mqtt_bridge.publish_active_sensors_list(devices_info)
        logger.info(f"📤 Inventario publicado a ThingsBoard: {len(devices_info)} dispositivos")
        
    except Exception as e:
        logger.error(f"❌ Error al publicar inventario: {e}", exc_info=True)


# ============================================================================
# RUTAS WEB (HTML)
# ============================================================================

@app.route('/')
def dashboard():
    """Dashboard principal"""
    return render_template('dashboard.html')


@app.route('/config')
def config():
    """Ventana de configuración"""
    return render_template('config.html')


@app.route('/polling')
def polling():
    """Ventana de polling en vivo"""
    return render_template('polling.html')


@app.route('/diagnostic')
def diagnostic():
    """Ventana de diagnóstico de dispositivos"""
    return render_template('diagnostic.html')


@app.route('/history')
def history():
    """Ventana de visualización de datos históricos"""
    return render_template('history.html')


# ============================================================================
# API REST - ADAPTADOR
# ============================================================================

@app.route('/api/adapter', methods=['GET'])
def api_adapter():
    """Info del adaptador USB-RS485"""
    if not modbus_master:
        return jsonify({'error': 'Modbus client not initialized'}), 500
    
    stats = modbus_master.get_stats()
    return jsonify(stats)


# ============================================================================
# API REST - DISPOSITIVOS
# ============================================================================

@app.route('/api/discover', methods=['POST'])
def api_discover():
    """Ejecuta discovery de dispositivos con progreso en tiempo real (en hilo separado)"""
    global discovery_state
    
    # Verificar si ya hay un discovery activo
    if discovery_state['active']:
        return jsonify({
            'status': 'error',
            'message': 'Ya hay un discovery en curso'
        }), 400
    
    data = request.get_json() or {}
    unit_id_min = data.get('unit_id_min', Config.DEVICE_UNIT_ID_MIN)
    unit_id_max = data.get('unit_id_max', Config.DEVICE_UNIT_ID_MAX)
    
    logger.info(f"Discovery solicitado: {unit_id_min}..{unit_id_max}")
    
    # Función que ejecuta el discovery en hilo separado
    def run_discovery():
        global discovery_state
        discovery_state['active'] = True
        discovery_state['total'] = unit_id_max - unit_id_min + 1
        
        # Callback para emitir progreso por WebSocket
        def progress_callback(current, total, unit_id):
            discovery_state['current'] = current
            discovery_state['unit_id'] = unit_id
            
            socketio.emit('discovery_progress', {
                'current': current,
                'total': total,
                'unit_id': unit_id,
                'percentage': int((current / total) * 100)
            })
        
        try:
            devices = device_manager.discover_devices(unit_id_min, unit_id_max, progress_callback=progress_callback)
            
            # Emitir evento de finalización
            socketio.emit('discovery_complete', {
                'devices_found': len(devices),
                'devices': [d.to_dict() for d in devices]
            })
            
            # NUEVO: Registrar sensores en base de datos
            if devices and database:
                _register_sensors_to_database(devices)
            
            # Si el polling está activo, añadir nuevos dispositivos automáticamente
            if devices and polling_service and polling_service.is_active():
                new_unit_ids = [d.unit_id for d in devices]
                current_unit_ids = polling_service.unit_ids or []
                
                # Encontrar dispositivos nuevos que no estén en polling
                truly_new = [uid for uid in new_unit_ids if uid not in current_unit_ids]
                
                if truly_new:
                    # Combinar dispositivos actuales con nuevos
                    combined_unit_ids = list(set(current_unit_ids + truly_new))
                    
                    logger.info(f"🔄 Discovery encontró {len(truly_new)} dispositivo(s) nuevo(s): {truly_new}")
                    logger.info(f"🔄 Reiniciando polling con lista actualizada: {combined_unit_ids}")
                    
                    # Reiniciar polling con la lista combinada
                    polling_service.stop()
                    import time
                    time.sleep(0.5)
                    
                    polling_service.start(
                        unit_ids=combined_unit_ids,
                        interval_sec=polling_service.interval_sec,
                        per_device_refresh_sec=polling_service.per_device_refresh_sec
                    )
                    
                    # Notificar al frontend
                    socketio.emit('polling_devices_updated', {
                        'unit_ids': combined_unit_ids,
                        'new_devices': truly_new
                    })
                    logger.info(f"✅ Polling actualizado con {len(truly_new)} dispositivo(s) nuevo(s)")
                else:
                    logger.info("ℹ️  No se encontraron dispositivos nuevos para añadir al polling")
            elif devices and polling_service and not polling_service.is_active():
                # Si polling no está activo pero hay dispositivos, iniciarlo
                unit_ids = [d.unit_id for d in devices]
                logger.info(f"🚀 Iniciando polling automático para {len(unit_ids)} dispositivo(s): {unit_ids}")
                
                polling_service.start(
                    unit_ids=unit_ids,
                    interval_sec=Config.POLL_INTERVAL_SEC,
                    per_device_refresh_sec=Config.PER_DEVICE_REFRESH_SEC
                )
                
                socketio.emit('polling_auto_started', {
                    'unit_ids': unit_ids,
                    'interval_sec': Config.POLL_INTERVAL_SEC
                })
                logger.info("✅ Polling iniciado automáticamente tras discovery")
                
        except Exception as e:
            logger.error(f"Error en discovery: {e}")
            socketio.emit('discovery_error', {'error': str(e)})
        finally:
            # Resetear estado
            discovery_state['active'] = False
            discovery_state['current'] = 0
            discovery_state['total'] = 0
            discovery_state['unit_id'] = 0
    
    # Ejecutar en hilo separado para no bloquear Flask
    discovery_thread = threading.Thread(target=run_discovery)
    discovery_thread.daemon = True
    discovery_thread.start()
    
    # Responder inmediatamente
    return jsonify({
        'status': 'started',
        'message': 'Discovery iniciado en segundo plano'
    })

@app.route('/api/discovery/status', methods=['GET'])
def api_discovery_status():
    """Consulta el estado actual del discovery"""
    return jsonify(discovery_state)


@app.route('/api/discovery/start', methods=['POST'])
def api_discovery_start():
    """
    Inicia un escaneo de discovery de dispositivos Modbus.
    
    Puede ser llamado desde:
    - Dashboard local (botón web)
    - ThingsBoard (control widget vía HTTP)
    - Scripts externos
    
    Returns:
        JSON con estado del discovery iniciado
    """
    global discovery_state
    
    if discovery_state['active']:
        return jsonify({
            'status': 'already_running',
            'message': 'Discovery ya está en ejecución',
            'progress': discovery_state
        }), 409
    
    try:
        # Lanzar discovery en thread separado
        import threading
        discovery_thread = threading.Thread(target=start_initial_discovery, daemon=True)
        discovery_thread.start()
        
        return jsonify({
            'status': 'started',
            'message': 'Discovery iniciado correctamente'
        })
    
    except Exception as e:
        logger.error(f"Error al iniciar discovery: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/devices', methods=['GET'])
def api_devices():
    """Lista todos los dispositivos en caché"""
    devices = device_manager.get_all_devices()
    return jsonify([d.to_dict() for d in devices])


@app.route('/api/mqtt/inventory/publish', methods=['POST'])
def api_publish_inventory():
    """
    Fuerza la publicación del inventario de dispositivos y sensores a ThingsBoard.
    
    Útil para:
    - Sincronizar manualmente después de cambios de configuración
    - Recuperación después de desconexiones MQTT
    - Testing/debugging de dashboards
    """
    try:
        _publish_sensors_inventory()
        return jsonify({
            'status': 'ok',
            'message': 'Inventario publicado a ThingsBoard correctamente'
        })
    except Exception as e:
        logger.error(f"Error al publicar inventario: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/devices/<int:unit_id>', methods=['GET'])
def api_device(unit_id):
    """Info de un dispositivo específico"""
    device = device_manager.get_device(unit_id)
    if not device:
        return jsonify({'error': 'Device not found'}), 404
    return jsonify(device.to_dict())


@app.route('/api/devices/<int:unit_id>/identify', methods=['POST'])
def api_identify(unit_id):
    """Activa LED de identificación y retorna información del dispositivo"""
    data = request.get_json() or {}
    duration_sec = data.get('duration_sec', 10)
    
    result = device_manager.identify_device(unit_id, duration_sec)
    if result['success']:
        return jsonify({
            'status': 'ok',
            'message': f'Identify activado en unit {unit_id} por ~5 segundos',
            'info': result['info']
        })
    else:
        return jsonify({'error': 'Failed to send identify command'}), 500


@app.route('/api/devices/<int:unit_id>/alias', methods=['PUT'])
def api_alias(unit_id):
    """Actualiza alias (solo escribe en RAM, no persiste)"""
    data = request.get_json() or {}
    alias = data.get('alias', '')
    
    if not alias:
        return jsonify({'error': 'Alias is required'}), 400
    
    # Solo escribe el alias en los registros Modbus (RAM)
    success = device_manager.write_alias_to_ram(unit_id, alias)
    if success:
        device = device_manager.get_device(unit_id)
        return jsonify({
            'status': 'ok',
            'message': 'Alias written to RAM (not persisted yet)',
            'device': device.to_dict() if device else None
        })
    else:
        return jsonify({'error': 'Failed to write alias'}), 500


@app.route('/api/devices/<int:unit_id>/save_eeprom', methods=['POST'])
def api_save_eeprom(unit_id):
    """Guarda configuración actual (UnitID + Alias) en EEPROM"""
    success = device_manager.save_to_eeprom(unit_id)
    if success:
        return jsonify({
            'status': 'ok',
            'message': f'Configuration saved to EEPROM for unit {unit_id}'
        })
    else:
        return jsonify({'error': 'Failed to save to EEPROM'}), 500


@app.route('/api/devices/<int:unit_id>/unit_id', methods=['PUT'])
def api_change_unit_id(unit_id):
    """Cambia Unit ID (solo escribe en RAM, no persiste)"""
    data = request.get_json() or {}
    new_unit_id = data.get('new_unit_id')
    
    if not new_unit_id or not (1 <= new_unit_id <= 247):
        return jsonify({'error': 'Invalid new_unit_id (must be 1..247)'}), 400
    
    success = device_manager.write_unit_id_to_ram(unit_id, new_unit_id)
    if success:
        device = device_manager.get_device(new_unit_id)
        return jsonify({
            'status': 'ok',
            'message': f'Unit ID changed from {unit_id} to {new_unit_id} (in RAM only)',
            'device': device.to_dict() if device else None
        })
    else:
        return jsonify({'error': 'Failed to change unit ID'}), 500


# ============================================================================
# API REST - LOAD SENSOR (TARE / CALIBRATE / HISTORY)
# ============================================================================

@app.route('/api/devices/<int:unit_id>/load/calibrate', methods=['POST'])
def api_load_calibrate(unit_id):
    """Calibra el factor del HX711 sin lectura raw: ajuste multiplicativo basado en lectura actual.
    Flujo:
      1) (Opcional) tare previo debe hacerse antes de colocar peso conocido.
      2) Usuario coloca un peso conocido (known_weight_kg).
      3) Leer factor actual (HR_LOAD_CAL_FACTOR_DECI) y la medida (IR_MED_PESO_KG).
      4) new_factor = old_factor * (measured_g / known_g).
      5) Escribir nuevo factor (en décimas) en HR_LOAD_CAL_FACTOR_DECI.
    """
    if not modbus_master:
        return jsonify({'error': 'Modbus client not initialized'}), 500

    data = request.get_json() or {}
    known_weight_kg = float(data.get('known_weight_kg', 0))
    if known_weight_kg <= 0:
        return jsonify({'error': 'known_weight_kg must be > 0'}), 400

    HR_LOAD_CAL_FACTOR_DECI = 0x0017
    IR_MED_PESO_KG = 0x000C

    # Leer factor actual
    regs = modbus_master.read_holding_registers(unit_id, HR_LOAD_CAL_FACTOR_DECI, 1)
    if not regs:
        return jsonify({'error': 'Failed to read current calibration factor'}), 503
    current_factor = regs[0] / 10.0

    # Leer medida actual (promedio implícito del firmware)
    import time as _t
    _t.sleep(0.25)
    ir = modbus_master.read_input_registers(unit_id, IR_MED_PESO_KG, 1)
    if not ir:
        return jsonify({'error': 'Failed to read current load measurement'}), 503
    # int16 → signed
    val = ir[0] if ir[0] < 32768 else ir[0] - 65536
    measured_kg = val / 100.0

    measured_g = measured_kg * 1000.0
    target_g = known_weight_kg * 1000.0
    if target_g <= 0.0:
        return jsonify({'error': 'Invalid known weight'}), 400

    # Si lectura es cero, abortar para evitar división por cero
    if measured_g == 0.0:
        return jsonify({'error': 'Measured weight is zero; ensure weight is on the scale and try again'}), 400

    new_factor = current_factor * (measured_g / target_g)
    # Limitar a rango admitido en firmware: 10.0 .. 2000.0
    new_factor = max(10.0, min(2000.0, new_factor))
    new_factor_deci = int(round(new_factor * 10.0))

    # Escribir nuevo factor
    ok = modbus_master.write_register(unit_id, HR_LOAD_CAL_FACTOR_DECI, new_factor_deci)
    if not ok:
        return jsonify({'error': 'Failed to write new calibration factor'}), 500

    # Verificación rápida
    _t.sleep(0.3)
    ir2 = modbus_master.read_input_registers(unit_id, IR_MED_PESO_KG, 1)
    if ir2:
        v2 = ir2[0] if ir2[0] < 32768 else ir2[0] - 65536
        measured2_kg = v2 / 100.0
    else:
        measured2_kg = None

    return jsonify({
        'status': 'ok',
        'known_weight_kg': known_weight_kg,
        'prev_factor': current_factor,
        'new_factor': new_factor,
        'new_factor_deci': new_factor_deci,
        'measured_before_kg': measured_kg,
        'measured_after_kg': measured2_kg
    })


@app.route('/api/devices/<int:unit_id>/load/max100', methods=['GET'])
def api_load_max100(unit_id):
    """Devuelve el máximo de las últimas 100 muestras desde firmware (IR_STAT_LOAD_MAX_KG)."""
    if not modbus_master:
        return jsonify({'error': 'Modbus client not initialized'}), 500
    IR_STAT_LOAD_MAX_KG = 0x001B
    regs = modbus_master.read_input_registers(unit_id, IR_STAT_LOAD_MAX_KG, 1)
    if not regs:
        return jsonify({'error': 'Failed to read max-of-100 from device'}), 503
    # int16
    val = regs[0] if regs[0] < 32768 else regs[0] - 65536
    return jsonify({'status': 'ok', 'unit_id': unit_id, 'max_kg': val / 100.0, 'raw': val})


# ============================================================================
# API REST - DIAGNOSTICS
# ============================================================================

@app.route('/api/diagnostics/<int:unit_id>', methods=['GET'])
def api_diagnostics(unit_id):
    """
    Lee información completa de diagnóstico de un dispositivo.
    
    Retorna:
        - Información básica (vendor, product, versiones, uptime)
        - Estado (ok, mpu_ready, cfg_dirty)
        - Errores activos (bitmask)
        - Capacidades (RS485, MPU6050, IDENTIFY)
        - Estadísticas Modbus (tramas RX/TX, errores CRC, excepciones)
        - Flags de calidad de medidas
    """
    from datetime import datetime
    
    try:
        # Leer info básica
        info = modbus_master.read_device_info(unit_id)
        if not info:
            logger.warning(f"No se pudo leer info de unit {unit_id}")
            return jsonify({'error': f'Device {unit_id} not responding'}), 503
        
        # Leer estadísticas Modbus
        diag = modbus_master.read_device_diagnostics(unit_id)
        if not diag:
            logger.warning(f"No se pudo leer diagnósticos de unit {unit_id}")
            return jsonify({'error': f'Device {unit_id} diagnostic registers not available'}), 503
        
        # Leer quality flags
        quality_flags = modbus_master.read_quality_flags(unit_id)
        
        # Decodificar bitmasks
        capabilities = modbus_master.decode_capabilities(info['capabilities'])
        status = modbus_master.decode_status(info['status'])
        
        # Obtener alias del device manager si está disponible
        device = device_manager.get_device(unit_id)
        alias = device.alias if device else ""
        
        # Construir respuesta
        result = {
            'unit_id': unit_id,
            'alias': alias,
            'vendor_id': info['vendor_id'],
            'product_id': info['product_id'],
            'hw_version': info['hw_version'],
            'fw_version': info['fw_version'],
            'uptime_seconds': info['uptime_s'],
            'capabilities': capabilities,
            'status': status,
            'errors': {
                'bitmask': info['errors'],
                'active': []  # TODO: decodificar errores específicos si es necesario
            },
            'modbus_stats': {
                'rx_ok': diag['rx_ok'],
                'crc_errors': diag['crc_errors'],
                'exceptions': diag['exceptions'],
                'tx_ok': diag['tx_ok'],
                'uart_overruns': diag['uart_overruns'],
                'last_exception': diag['last_exception']
            },
            'quality_flags': quality_flags,
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Error al leer diagnósticos de unit {unit_id}: {e}", exc_info=True)
        return jsonify({'error': f'Internal error: {str(e)}'}), 500


# ============================================================================
# API REST - POLLING
# ============================================================================

@app.route('/api/polling/start', methods=['POST'])
def api_polling_start():
    """Inicia polling automático"""
    data = request.get_json() or {}
    unit_ids = data.get('unit_ids', [])
    interval_sec = data.get('interval_sec', Config.POLL_INTERVAL_SEC)
    per_device_refresh_sec = data.get('per_device_refresh_sec', Config.PER_DEVICE_REFRESH_SEC)
    
    if not unit_ids:
        return jsonify({'error': 'unit_ids is required'}), 400
    
    try:
        polling_service.start(unit_ids, interval_sec, per_device_refresh_sec)
        return jsonify({
            'status': 'started',
            'interval_sec': interval_sec,
            'per_device_refresh_sec': per_device_refresh_sec,
            'devices': unit_ids
        })
    except Exception as e:
        logger.error(f"Error al iniciar polling: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/polling/stop', methods=['POST'])
def api_polling_stop():
    """Detiene polling automático"""
    polling_service.stop()
    return jsonify({'status': 'stopped'})


@app.route('/api/polling/status', methods=['GET'])
def api_polling_status():
    """Estado del polling"""
    status = polling_service.get_status()
    return jsonify(status)


# ============================================================================
# API REST - WIND TELEMETRY
# ============================================================================

@app.route('/api/wind/<int:unit_id>', methods=['GET'])
def api_wind(unit_id):
    """Última telemetría de viento para un dispositivo (si disponible)."""
    if not polling_service:
        return jsonify({'error': 'PollingService not initialized'}), 500
    data = polling_service.get_last_wind(unit_id)
    if not data:
        return jsonify({'error': 'No wind data'}), 404
    return jsonify({'status': 'ok', **data})

@app.route('/api/stats/<int:unit_id>', methods=['GET'])
def api_stats(unit_id):
    """Últimas estadísticas de ventanas (viento y aceleración) si están disponibles."""
    if not polling_service:
        return jsonify({'error': 'PollingService not initialized'}), 500
    data = polling_service.get_last_stats(unit_id)
    if not data:
        return jsonify({'error': 'No stats available'}), 404
    return jsonify({'status': 'ok', **data})

# ============================================================================
# API REST - HEALTH
# ============================================================================

@app.route('/api/health', methods=['GET'])
def api_health():
    """Estado del Edge"""
    return jsonify({
        'status': 'healthy',
        'modbus': {
            'connected': modbus_master.is_connected() if modbus_master else False,
            'port': modbus_master.port if modbus_master else None
        },
        'polling': {
            'active': polling_service.is_active() if polling_service else False,
            'devices_monitored': len(polling_service.unit_ids) if polling_service else 0
        }
    })


# ============================================================================
# WEBSOCKET HANDLERS
# ============================================================================

@socketio.on('connect')
def handle_connect():
    """Cliente WebSocket conectado"""
    logger.info("Cliente WebSocket conectado")
    emit('connection_response', {'status': 'connected'})


@socketio.on('disconnect')
def handle_disconnect():
    """Cliente WebSocket desconectado"""
    logger.info("Cliente WebSocket desconectado")


# ============================================================================
# API REST - HISTORIAL (DATABASE)
# ============================================================================

@app.route('/api/history/stats', methods=['GET'])
def api_history_stats():
    """Estadísticas de la base de datos"""
    if not database:
        return jsonify({'error': 'Database not available'}), 500
    
    try:
        stats = database.get_db_stats()
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error getting DB stats: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/history/devices', methods=['GET'])
def api_history_devices():
    """Lista de dispositivos registrados en la BD"""
    if not database:
        return jsonify({'error': 'Database not available'}), 500
    
    try:
        devices = database.get_all_devices(enabled_only=False)
        return jsonify({'devices': devices})
    except Exception as e:
        logger.error(f"Error getting devices: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/history/sensors/<int:unit_id>', methods=['GET'])
def api_history_sensors(unit_id):
    """Sensores de un dispositivo específico"""
    if not database:
        return jsonify({'error': 'Database not available'}), 500
    
    try:
        device = database.get_device(unit_id)
        if not device:
            return jsonify({'error': 'Device not found'}), 404
        
        sensors = database.get_sensors_by_device(unit_id, enabled_only=False)
        return jsonify({
            'device': device,
            'sensors': sensors
        })
    except Exception as e:
        logger.error(f"Error getting sensors for device {unit_id}: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/history/data/<sensor_id>', methods=['GET'])
def api_history_data(sensor_id):
    """Datos históricos de un sensor"""
    if not database:
        return jsonify({'error': 'Database not available'}), 500
    
    try:
        # Obtener parámetros de tiempo
        hours = request.args.get('hours', type=int)
        start_str = request.args.get('start')
        end_str = request.args.get('end')
        
        # Determinar rango temporal
        if start_str and end_str:
            # Rango personalizado
            from datetime import datetime
            start_time = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
            end_time = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
            
            # Obtener medidas en el rango
            measurements = database.get_measurements(
                sensor_id=sensor_id,
                since=start_time,
                limit=10000  # Límite alto para rango personalizado
            )
            
            # Filtrar por end_time manualmente
            measurements = [m for m in measurements if m['timestamp'] <= end_time.isoformat() + 'Z']
            
        elif hours:
            # Rango por horas desde ahora
            from datetime import datetime, timedelta
            since = datetime.utcnow() - timedelta(hours=hours)
            measurements = database.get_measurements(
                sensor_id=sensor_id,
                since=since,
                limit=10000
            )
        else:
            # Por defecto: últimas 24 horas
            from datetime import datetime, timedelta
            since = datetime.utcnow() - timedelta(hours=24)
            measurements = database.get_measurements(
                sensor_id=sensor_id,
                since=since,
                limit=10000
            )
        
        if not measurements:
            return jsonify({
                'sensor_id': sensor_id,
                'measurements': [],
                'stats': {
                    'count': 0,
                    'min': 0,
                    'max': 0,
                    'avg': 0
                },
                'unit': ''
            })
        
        # Calcular estadísticas
        values = [m['value'] for m in measurements]
        stats = {
            'count': len(values),
            'min': min(values),
            'max': max(values),
            'avg': sum(values) / len(values)
        }
        
        # Obtener unidad del primer measurement
        unit = measurements[0]['unit'] if measurements else ''
        
        return jsonify({
            'sensor_id': sensor_id,
            'measurements': measurements,
            'stats': stats,
            'unit': unit
        })
        
    except Exception as e:
        logger.error(f"Error getting data for sensor {sensor_id}: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# API: ALERTAS
# ============================================================================

@app.route('/api/alerts', methods=['GET'])
def api_get_alerts():
    """
    Obtiene alertas con filtros opcionales.
    
    Query params:
        - ack: "true" (reconocidas) / "false" (activas) / omitir (todas)
        - level: "INFO" / "WARN" / "ALARM" / "CRITICAL"
        - limit: Número máximo de alertas (default: 100)
    
    Returns:
        JSON: Lista de alertas
    
    Example:
        GET /api/alerts?ack=false&level=ALARM&limit=50
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
                },
                ...
            ],
            "count": 50
        }
    """
    if not database:
        return jsonify({'error': 'Database not initialized'}), 500
    
    try:
        # Parsear parámetros de query
        ack_str = request.args.get('ack')
        level = request.args.get('level')
        limit = int(request.args.get('limit', 100))
        
        # Convertir ack a bool si está presente
        ack = None
        if ack_str == 'true':
            ack = True
        elif ack_str == 'false':
            ack = False
        
        # Obtener alertas
        alerts = database.get_alerts(ack=ack, level=level, limit=limit)
        
        return jsonify({
            'alerts': alerts,
            'count': len(alerts)
        })
    
    except ValueError as e:
        return jsonify({'error': f'Invalid parameter: {e}'}), 400
    except Exception as e:
        logger.error(f"Error getting alerts: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/alerts/<int:alert_id>/acknowledge', methods=['POST'])
def api_acknowledge_alert(alert_id: int):
    """
    Marca una alerta como reconocida.
    
    Args:
        alert_id: ID de la alerta
    
    Returns:
        JSON: Confirmación
    
    Example:
        POST /api/alerts/123/acknowledge
        {
            "success": true,
            "alert_id": 123,
            "message": "Alert acknowledged"
        }
    """
    if not database or not alert_engine:
        return jsonify({'error': 'Services not initialized'}), 500
    
    try:
        alert_engine.acknowledge_alert(alert_id)
        
        return jsonify({
            'success': True,
            'alert_id': alert_id,
            'message': 'Alert acknowledged'
        })
    
    except Exception as e:
        logger.error(f"Error acknowledging alert {alert_id}: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/alerts/stats', methods=['GET'])
def api_alert_stats():
    """
    Obtiene estadísticas de alertas.
    
    Returns:
        JSON: Estadísticas de alertas
    
    Example:
        GET /api/alerts/stats
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
    """
    if not alert_engine:
        return jsonify({'error': 'Alert engine not initialized'}), 500
    
    try:
        stats = alert_engine.get_alert_stats()
        return jsonify(stats)
    
    except Exception as e:
        logger.error(f"Error getting alert stats: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/alerts/clear-all', methods=['POST'])
def api_clear_all_alerts():
    """
    Auto-reconoce TODAS las alertas activas del sistema.
    
    Returns:
        JSON: Número de alertas reconocidas
    
    Example:
        POST /api/alerts/clear-all
        {
            "cleared": 36,
            "message": "36 alertas reconocidas"
        }
    """
    if not alert_engine or not database:
        return jsonify({'error': 'Services not initialized'}), 500
    
    try:
        # Obtener todas las alertas activas
        active_alerts = database.get_alerts(ack=False, limit=10000)
        cleared_count = 0
        
        for alert in active_alerts:
            alert_id = alert.get('id')
            database.acknowledge_alert(alert_id)
            cleared_count += 1
            
            # Emitir evento de reconocimiento
            if socketio:
                socketio.emit('alert_acknowledged', {
                    'alert_id': alert_id,
                    'auto': True,
                    'reason': 'Limpieza masiva manual'
                }, namespace='/')
        
        logger.warning(f"🧹 Limpieza masiva: {cleared_count} alertas reconocidas manualmente")
        
        return jsonify({
            'cleared': cleared_count,
            'message': f'{cleared_count} alertas reconocidas'
        })
    
    except Exception as e:
        logger.error(f"Error clearing all alerts: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/alerts/clear-device/<int:unit_id>', methods=['POST'])
def api_clear_device_alerts(unit_id):
    """
    Auto-reconoce todas las alertas de un dispositivo específico.
    
    Args:
        unit_id: ID del dispositivo
    
    Returns:
        JSON: Número de alertas reconocidas
    
    Example:
        POST /api/alerts/clear-device/2
        {
            "cleared": 12,
            "message": "12 alertas del dispositivo 2 reconocidas"
        }
    """
    if not alert_engine:
        return jsonify({'error': 'Alert engine not initialized'}), 500
    
    try:
        alert_engine.clear_device_alerts(unit_id)
        
        return jsonify({
            'unit_id': unit_id,
            'message': f'Alertas del dispositivo {unit_id} reconocidas'
        })
    
    except Exception as e:
        logger.error(f"Error clearing device alerts: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Punto de entrada principal"""
    import sys
    
    logger.info("=== Iniciando Edge Layer ===")
    logger.info(f"Puerto: {Config.MODBUS_PORT}")
    logger.info(f"Baudrate: {Config.MODBUS_BAUDRATE}")
    logger.info(f"Flask: {Config.FLASK_HOST}:{Config.FLASK_PORT}")
    
    # Verificar si se solicitó auto-reload
    use_reloader = '--reload' in sys.argv
    
    if use_reloader:
        logger.info("⚡ Modo auto-reload activado (watchdog)")
        # Instalar watchdog para recargar en cambios
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler
            import os
            
            class ReloadHandler(FileSystemEventHandler):
                def on_modified(self, event):
                    if event.src_path.endswith('.py'):
                        logger.info(f"📝 Archivo modificado: {event.src_path}")
                        logger.info("🔄 Recargando servidor...")
                        os.execv(sys.executable, ['python'] + sys.argv)
            
            # Observar directorio src/
            src_dir = os.path.dirname(os.path.abspath(__file__))
            observer = Observer()
            observer.schedule(ReloadHandler(), path=src_dir, recursive=False)
            observer.start()
            logger.info(f"👁️  Observando cambios en: {src_dir}")
        except ImportError:
            logger.warning("⚠️  watchdog no instalado. Auto-reload deshabilitado.")
            logger.warning("   Instala con: pip install watchdog")
            use_reloader = False
    
    # Inicializar Modbus Master y servicios
    ok = init_modbus()
    if ok:
        # Lanzar discovery inicial en background
        start_initial_discovery()
    
    # Ejecutar Flask app
    logger.info("Iniciando servidor Flask...")
    socketio.run(
        app,
        host=Config.FLASK_HOST,
        port=Config.FLASK_PORT,
        debug=Config.FLASK_DEBUG,
        use_reloader=False,  # Siempre False, usamos watchdog personalizado
        allow_unsafe_werkzeug=True
    )


if __name__ == '__main__':
    main()
