"""
Flask App principal - Edge Layer.
Rutas web y API REST para gestión de dispositivos Modbus.
"""
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
from config import Config
from logger import logger
from modbus_master import ModbusMaster
from device_manager import DeviceManager
from data_normalizer import DataNormalizer
from polling_service import PollingService
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

# Estado del discovery
discovery_state = {
    'active': False,
    'current': 0,
    'total': 0,
    'unit_id': 0
}


def init_modbus():
    """Inicializa el Modbus Master RTU y servicios"""
    global modbus_master, device_manager, polling_service
    
    # Determinar puerto (manual o autodetección)
    port = Config.MODBUS_PORT
    if port == 'auto':
        logger.warning("Puerto configurado como 'auto', pero autodetección deshabilitada por usuario")
        logger.warning("Configura MODBUS_PORT en .env con el puerto correcto (ej: /dev/tty.usbmodem5A300455411)")
        return False
    
    logger.info(f"Inicializando Modbus Master en {port} @ {Config.MODBUS_BAUDRATE} baud")
    
    # Crear instancias
    modbus_master = ModbusMaster(port=port, baudrate=Config.MODBUS_BAUDRATE)
    
    # Conectar al puerto serie
    if not modbus_master.connect():
        logger.error("No se pudo conectar al puerto serie. Verifica el cable y el puerto.")
        return False
    
    device_manager = DeviceManager(modbus_master, DataNormalizer())
    polling_service = PollingService(modbus_master, device_manager)
    
    # Conectar callbacks para WebSocket
    polling_service.on_telemetry_callback = emit_telemetry
    polling_service.on_diagnostic_callback = emit_diagnostic
    
    logger.info("DeviceManager y PollingService inicializados")
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
            socketio.emit('discovery_complete', {
                'devices_found': len(devices),
                'devices': [d.to_dict() for d in devices]
            })
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


def emit_telemetry(telemetry_data: dict):
    """Emite telemetría vía WebSocket"""
    socketio.emit('telemetry_update', telemetry_data, namespace='/')
    logger.debug(f"📡 WebSocket emit: telemetry_update para unit {telemetry_data.get('unit_id')}")


def emit_diagnostic(diagnostic_data: dict):
    """Emite diagnósticos vía WebSocket"""
    socketio.emit('diagnostic_update', diagnostic_data, namespace='/')
    logger.debug(f"🔍 WebSocket emit: diagnostic_update para unit {diagnostic_data.get('unit_id')}")


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


@app.route('/api/devices', methods=['GET'])
def api_devices():
    """Lista todos los dispositivos en caché"""
    devices = device_manager.get_all_devices()
    return jsonify([d.to_dict() for d in devices])


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
