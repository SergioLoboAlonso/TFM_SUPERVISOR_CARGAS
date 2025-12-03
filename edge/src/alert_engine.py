"""
============================================================================
ALERT ENGINE - Motor de Alertas para Edge Layer
============================================================================

Responsabilidades:
    1. Monitoreo de umbrales de sensores (alarm_lo, alarm_hi)
    2. Detección de dispositivos offline (last_seen timeout)
    3. Generación automática de alertas en BD
    4. Notificación en tiempo real vía SocketIO
    5. Debouncing para evitar spam de alertas

Arquitectura:
    PollingService ──> AlertEngine.check_measurement()
                           │
                           ├─> Verifica umbrales alarm_lo/alarm_hi
                           ├─> Inserta alerta en BD si aplica
                           └─> Emite evento SocketIO 'new_alert'
    
    Thread periódico ──> AlertEngine.check_device_status()
                           │
                           ├─> Verifica last_seen de devices
                           └─> Genera alerta si timeout excedido

Configuración:
    - DEVICE_TIMEOUT: Segundos sin telemetría para marcar offline (default: 30s)
    - DEBOUNCE_WINDOW: Segundos entre alertas del mismo sensor (default: 60s)
    - MAX_ALERTS_PER_HOUR: Límite de alertas por sensor/hora (default: 20)

============================================================================
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from logger import logger
from database import Database
import threading
import time


# ============================================================================
# CONFIGURACIÓN
# ============================================================================

# Timeout para considerar dispositivo offline (segundos)
DEVICE_TIMEOUT = 30  # 30 segundos sin telemetría

# Ventana de debouncing para evitar spam de alertas (segundos)
DEBOUNCE_WINDOW = 60  # 1 minuto entre alertas del mismo tipo/sensor

# Límite de alertas por sensor por hora (anti-flood)
MAX_ALERTS_PER_HOUR = 20


# ============================================================================
# ALERT ENGINE
# ============================================================================

class AlertEngine:
    """
    Motor de alertas para el Edge Layer.
    Monitorea medidas y estado de dispositivos, generando alertas automáticas.
    """
    
    def __init__(self, database: Database, socketio=None, mqtt_bridge=None, polling_service=None):
        """
        Inicializa el motor de alertas.
        
        Args:
            database: Instancia de Database para acceso a BD
            socketio: Instancia de SocketIO para notificaciones en tiempo real (opcional)
            mqtt_bridge: Instancia de MQTTBridge para publicación IoT (opcional)
            polling_service: Instancia de PollingService para verificar dispositivos activos (opcional)
        """
        self.db = database
        self.socketio = socketio
        self.mqtt_bridge = mqtt_bridge
        self.polling_service = polling_service
        
        # Cache de última alerta por (sensor_id, code) para debouncing
        # Estructura: {(sensor_id, code): timestamp_ultimo_alert}
        self._last_alert_cache = {}
        
        # Cache de alertas activas por sensor para auto-resolución
        # Estructura: {(sensor_id, code): alert_id}
        self._active_alerts_cache = {}
        
        # Thread para monitoreo de estado de dispositivos
        self._monitoring_thread = None
        self._monitoring_active = False
        
        # Reconstruir cache de alertas activas desde BD
        self._rebuild_active_alerts_cache()
        
        logger.info("🚨 AlertEngine inicializado")
    
    
    # ========================================================================
    # MONITOREO DE UMBRALES DE MEDIDAS
    # ========================================================================
    
    def check_measurement_thresholds(
        self,
        sensor_id: str,
        value: float,
        sensor_config: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Verifica si una medida viola umbrales de alarma.
        
        Args:
            sensor_id: ID del sensor (ej: "UNIT_2_TILT_X")
            value: Valor medido
            sensor_config: Dict con 'alarm_lo', 'alarm_hi', 'unit', 'unit_id', 'type'
        
        Returns:
            Dict con alerta generada, o None si no aplica
        
        Example:
            sensor_config = {
                'sensor_id': 'UNIT_2_TILT_X',
                'alarm_lo': -5.0,
                'alarm_hi': 5.0,
                'unit': 'deg',
                'unit_id': 2,
                'type': 'tilt'
            }
            alert = engine.check_measurement_thresholds('UNIT_2_TILT_X', 6.2, sensor_config)
            # alert = {'level': 'ALARM', 'code': 'THRESHOLD_EXCEEDED_HI', ...}
        """
        alarm_lo = sensor_config.get('alarm_lo')
        alarm_hi = sensor_config.get('alarm_hi')
        unit = sensor_config.get('unit', '')
        unit_id = sensor_config.get('unit_id')
        
        # Si no hay umbrales configurados, no hay alerta
        if alarm_lo is None and alarm_hi is None:
            return None
        
        # Verificar si hay alertas activas de umbral para este sensor
        cache_key_lo = (sensor_id, "THRESHOLD_EXCEEDED_LO")
        cache_key_hi = (sensor_id, "THRESHOLD_EXCEEDED_HI")
        
        # AUTO-RESOLUCIÓN: Si el valor ahora está dentro del rango, reconocer alertas activas
        value_in_range = True
        
        if alarm_lo is not None and value < alarm_lo:
            value_in_range = False
        elif alarm_hi is not None and value > alarm_hi:
            value_in_range = False
        
        if value_in_range:
            # AUTO-RESOLUCIÓN: Valor dentro de rango normal
            # Buscar TODAS las alertas activas de este tipo (puede haber duplicados)
            self._auto_acknowledge_all_alerts(sensor_id, "THRESHOLD_EXCEEDED_LO",
                f"Valor normalizado: {value:.2f} {unit}")
            self._auto_acknowledge_all_alerts(sensor_id, "THRESHOLD_EXCEEDED_HI",
                f"Valor normalizado: {value:.2f} {unit}")
            
            # Limpiar cache
            if cache_key_lo in self._active_alerts_cache:
                del self._active_alerts_cache[cache_key_lo]
            if cache_key_hi in self._active_alerts_cache:
                del self._active_alerts_cache[cache_key_hi]
            
            return None  # No generar alerta si está en rango normal
        
        # Valor FUERA de rango, determinar tipo de violación
        if alarm_lo is not None and value < alarm_lo:
            code = "THRESHOLD_EXCEEDED_LO"
            level = "ALARM"
            message = (
                f"Sensor {sensor_id}: valor {value:.2f} {unit} "
                f"por debajo del umbral inferior {alarm_lo:.2f} {unit}"
            )
        
        elif alarm_hi is not None and value > alarm_hi:
            code = "THRESHOLD_EXCEEDED_HI"
            level = "ALARM"
            message = (
                f"Sensor {sensor_id}: valor {value:.2f} {unit} "
                f"supera el umbral superior {alarm_hi:.2f} {unit}"
            )
        else:
            return None
        
        # Debouncing: evitar spam de alertas del mismo tipo
        if not self._should_create_alert(sensor_id, code):
            logger.debug(f"Alerta {code} para {sensor_id} en debounce, ignorando")
            return None
        
        # Crear alerta
        alert_data = {
            'sensor_id': sensor_id,
            'rig_id': f"RIG_01",  # TODO: Obtener de sensor_config
            'level': level,
            'code': code,
            'message': message
        }
        
        # Insertar en BD
        alert_id = self._create_alert(alert_data)
        alert_data['id'] = alert_id
        
        # Registrar en cache de alertas activas para auto-resolución
        cache_key = (sensor_id, code)
        self._active_alerts_cache[cache_key] = alert_id
        
        # Notificar vía SocketIO si está disponible
        if self.socketio:
            self._emit_alert(alert_data)
        
        logger.warning(f"⚠️  ALERTA: {message}")
        return alert_data
    
    
    # ========================================================================
    # MONITOREO DE ESTADO DE DISPOSITIVOS
    # ========================================================================
    
    def check_device_status(self) -> List[Dict[str, Any]]:
        """
        Verifica el estado de todos los dispositivos habilitados.
        Genera alertas para dispositivos offline (last_seen > timeout).
        
        Returns:
            Lista de alertas generadas
        
        Example:
            alerts = engine.check_device_status()
            # alerts = [
            #     {'level': 'WARN', 'code': 'DEVICE_OFFLINE', 'message': '...'},
            #     ...
            # ]
        """
        alerts_generated = []
        devices = self.db.get_all_devices()
        now = datetime.utcnow()  # Naive UTC
        
        # Obtener lista de dispositivos activos en polling (si disponible)
        active_unit_ids = []
        if self.polling_service and hasattr(self.polling_service, 'unit_ids'):
            active_unit_ids = self.polling_service.unit_ids
            logger.debug(f"AlertEngine: Monitoreando solo dispositivos activos en polling: {active_unit_ids}")
        else:
            logger.warning(f"AlertEngine: No se pudo obtener lista de dispositivos activos, monitoreando TODOS")
        
        for device in devices:
            if not device.get('enabled', 1):
                continue  # Ignorar dispositivos deshabilitados
            
            unit_id = device['unit_id']
            
            # CRÍTICO: Solo monitorear dispositivos que están en polling activo
            if active_unit_ids and unit_id not in active_unit_ids:
                logger.debug(f"AlertEngine: Ignorando dispositivo unit_{unit_id} (no está en polling activo)")
                continue  # Dispositivo no está siendo polleado, ignorar
            alias = device['alias']
            last_seen_str = device['last_seen']
            
            # Parsear last_seen (formato ISO8601)
            try:
                # Parsear datetime y hacerlo naive para comparación
                last_seen_str_clean = last_seen_str.replace('Z', '+00:00')
                last_seen = datetime.fromisoformat(last_seen_str_clean)
                
                # Convertir a naive UTC si es aware
                if last_seen.tzinfo is not None:
                    last_seen = last_seen.replace(tzinfo=None)
                    
            except (ValueError, AttributeError):
                logger.error(f"Formato inválido de last_seen para unit {unit_id}: {last_seen_str}")
                continue
            
            # Calcular tiempo sin telemetría
            elapsed = (now - last_seen).total_seconds()
            
            # Cache key para alertas de dispositivo
            cache_key = (f"device_{unit_id}", "DEVICE_OFFLINE")
            
            # AUTO-RESOLUCIÓN: Si el dispositivo está online
            if elapsed <= DEVICE_TIMEOUT:
                # Buscar TODAS las alertas DEVICE_OFFLINE activas de este dispositivo
                device_key = f"device_{unit_id}"
                self._auto_acknowledge_all_alerts(device_key, "DEVICE_OFFLINE",
                    f"Dispositivo {alias} (Unit {unit_id}) vuelve online")
                
                # Limpiar cache
                if cache_key in self._active_alerts_cache:
                    del self._active_alerts_cache[cache_key]
                continue  # Dispositivo online, no generar alerta
            
            # Si excede timeout, generar alerta
            code = "DEVICE_OFFLINE"
            level = "WARN"
            message = (
                f"Dispositivo {alias} (Unit {unit_id}) sin telemetría "
                f"desde hace {int(elapsed)}s (timeout: {DEVICE_TIMEOUT}s)"
            )
            
            # Debouncing
            cache_key = f"device_{unit_id}"
            if not self._should_create_alert(cache_key, code):
                continue
            
            # Crear alerta
            alert_data = {
                'rig_id': device.get('rig_id', 'UNKNOWN'),
                'level': level,
                'code': code,
                'message': message
            }
            
            alert_id = self._create_alert(alert_data)
            alert_data['id'] = alert_id
            alerts_generated.append(alert_data)
            
            # Registrar en cache de alertas activas
            alert_cache_key = (f"device_{unit_id}", code)
            self._active_alerts_cache[alert_cache_key] = alert_id
            
            # Notificar vía SocketIO
            if self.socketio:
                self._emit_alert(alert_data)
            
            logger.warning(f"⚠️  {message}")
        
        return alerts_generated
    
    
    # ========================================================================
    # MONITOREO CONTINUO (THREAD)
    # ========================================================================
    
    def start_monitoring(self, interval: int = 10):
        """
        Inicia thread de monitoreo continuo de estado de dispositivos.
        
        Args:
            interval: Intervalo de verificación en segundos (default: 10s)
        """
        if self._monitoring_active:
            logger.warning("Monitoreo de alertas ya está activo")
            return
        
        self._monitoring_active = True
        self._monitoring_thread = threading.Thread(
            target=self._monitoring_loop,
            args=(interval,),
            daemon=True,
            name="AlertEngine-Monitor"
        )
        self._monitoring_thread.start()
        logger.info(f"🔄 Monitoreo de alertas iniciado (intervalo: {interval}s)")
    
    
    def stop_monitoring(self):
        """Detiene el thread de monitoreo."""
        if not self._monitoring_active:
            return
        
        self._monitoring_active = False
        if self._monitoring_thread:
            self._monitoring_thread.join(timeout=5)
        logger.info("🛑 Monitoreo de alertas detenido")
    
    
    def _monitoring_loop(self, interval: int):
        """Loop principal del thread de monitoreo."""
        logger.info("🔍 Thread de monitoreo de alertas iniciado")
        
        while self._monitoring_active:
            try:
                # Verificar estado de dispositivos
                self.check_device_status()
                
            except Exception as e:
                logger.error(f"Error en monitoreo de alertas: {e}", exc_info=True)
            
            # Esperar intervalo
            time.sleep(interval)
        
        logger.info("🔍 Thread de monitoreo de alertas finalizado")
    
    
    # ========================================================================
    # MÉTODOS AUXILIARES
    # ========================================================================
    
    def _should_create_alert(self, entity_id: str, code: str) -> bool:
        """
        Verifica si se debe crear una alerta basado en debouncing.
        
        Args:
            entity_id: ID del sensor o dispositivo
            code: Código de alerta (ej: "THRESHOLD_EXCEEDED_HI")
        
        Returns:
            True si se debe crear la alerta, False si está en ventana de debounce
        """
        cache_key = (entity_id, code)
        last_alert_time = self._last_alert_cache.get(cache_key)
        
        if last_alert_time is None:
            # Primera alerta de este tipo
            self._last_alert_cache[cache_key] = datetime.utcnow()
            return True
        
        # Verificar si ha pasado la ventana de debouncing
        elapsed = (datetime.utcnow() - last_alert_time).total_seconds()
        
        if elapsed < DEBOUNCE_WINDOW:
            return False  # Aún en ventana de debounce
        
        # Ha pasado el tiempo de debounce, permitir nueva alerta
        self._last_alert_cache[cache_key] = datetime.utcnow()
        return True
    
    
    def _create_alert(self, alert_data: Dict[str, Any]) -> int:
        """
        Inserta una alerta en la base de datos.
        
        Args:
            alert_data: Dict con campos de alerta
        
        Returns:
            ID de la alerta insertada
        """
        try:
            alert_id = self.db.insert_alert(alert_data)
            logger.debug(f"Alerta {alert_id} insertada en BD: {alert_data['code']}")
            return alert_id
        
        except Exception as e:
            logger.error(f"Error al insertar alerta en BD: {e}", exc_info=True)
            return -1
    
    
    def _emit_alert(self, alert_data: Dict[str, Any]):
        """
        Emite una alerta vía SocketIO y MQTT para notificación en tiempo real.
        
        Args:
            alert_data: Dict con datos de la alerta
        """
        try:
            # Formatear timestamp para frontend
            if 'timestamp' not in alert_data:
                alert_data['timestamp'] = datetime.utcnow().isoformat() + 'Z'
            
            # Emitir evento SocketIO
            if self.socketio:
                self.socketio.emit('new_alert', alert_data, namespace='/')
                logger.debug(f"Alerta emitida vía SocketIO: {alert_data['code']}")
            
            # Publicar a MQTT
            if self.mqtt_bridge:
                # Extraer device_id desde sensor_id o mensaje
                device_id = None
                sensor_id = alert_data.get('sensor_id')
                
                if sensor_id and '_' in sensor_id:
                    # Formato: UNIT_2_TILT_X -> unit_2
                    parts = sensor_id.split('_')
                    if len(parts) >= 2 and parts[0] == 'UNIT':
                        device_id = f"unit_{parts[1]}"
                
                # Si no hay sensor_id, buscar en mensaje (ej: "Unit 2")
                if not device_id:
                    import re
                    message = alert_data.get('message', '')
                    match = re.search(r'Unit (\d+)', message)
                    if match:
                        device_id = f"unit_{match.group(1)}"
                
                self.mqtt_bridge.publish_alert(
                    alert_id=alert_data.get('id'),
                    level=alert_data.get('level'),
                    code=alert_data.get('code'),
                    message=alert_data.get('message'),
                    device_id=device_id,
                    sensor_id=sensor_id,
                    timestamp=alert_data['timestamp'],
                    ack=False
                )
        
        except Exception as e:
            logger.error(f"Error al emitir alerta: {e}", exc_info=True)
    
    
    def _auto_acknowledge_alert(self, alert_id: int, sensor_id: Optional[str], code: str, reason: str):
        """
        Auto-reconoce una alerta cuando la condición se resuelve.
        
        Args:
            alert_id: ID de la alerta a reconocer
            sensor_id: ID del sensor (o None si es alerta de sistema)
            code: Código de la alerta
            reason: Razón de la resolución
        """
        try:
            self.db.acknowledge_alert(alert_id)
            
            entity = sensor_id if sensor_id else "sistema"
            logger.info(f"✅ Auto-resolución: Alerta {alert_id} ({code}) para {entity} reconocida - {reason}")
            
            # Emitir evento de reconocimiento
            if self.socketio:
                self.socketio.emit('alert_acknowledged', {
                    'alert_id': alert_id,
                    'auto': True,
                    'reason': reason
                }, namespace='/')
        
        except Exception as e:
            logger.error(f"Error al auto-reconocer alerta {alert_id}: {e}", exc_info=True)
    
    
    def _auto_acknowledge_all_alerts(self, sensor_or_device_id: str, code: str, reason: str):
        """
        Auto-reconoce TODAS las alertas activas del mismo tipo (sensor/dispositivo + código).
        
        Esto resuelve el problema de alertas duplicadas que no están en el cache.
        
        Args:
            sensor_or_device_id: ID del sensor (ej: "UNIT_2_TILT_X") o dispositivo (ej: "device_2")
            code: Código de alerta (ej: "THRESHOLD_EXCEEDED_LO", "DEVICE_OFFLINE")
            reason: Razón de la resolución automática
        """
        try:
            # Buscar TODAS las alertas activas de este tipo en la BD
            active_alerts = self.db.get_alerts(ack=False, limit=1000)
            
            resolved_count = 0
            for alert in active_alerts:
                alert_id = alert.get('id')
                alert_sensor_id = alert.get('sensor_id')
                alert_code = alert.get('code')
                
                # Verificar coincidencia
                match = False
                
                if alert_sensor_id == sensor_or_device_id and alert_code == code:
                    # Alerta de sensor
                    match = True
                elif alert_code == code and sensor_or_device_id.startswith('device_'):
                    # Alerta de dispositivo: verificar en mensaje
                    message = alert.get('message', '')
                    unit_id = sensor_or_device_id.replace('device_', '')
                    if f"Unit {unit_id}" in message:
                        match = True
                
                if match:
                    # Auto-reconocer esta alerta
                    self.db.acknowledge_alert(alert_id)
                    resolved_count += 1
                    
                    # Emitir evento de reconocimiento
                    if self.socketio:
                        self.socketio.emit('alert_acknowledged', {
                            'alert_id': alert_id,
                            'auto': True,
                            'reason': reason
                        }, namespace='/')
            
            if resolved_count > 0:
                entity = sensor_or_device_id
                logger.info(f"✅ Auto-resolución masiva: {resolved_count} alerta(s) ({code}) para {entity} reconocidas - {reason}")
        
        except Exception as e:
            logger.error(f"Error en auto-resolución masiva para {sensor_or_device_id}/{code}: {e}", exc_info=True)
    
    
    def _rebuild_active_alerts_cache(self):
        """
        Reconstruye el cache de alertas activas desde la base de datos.
        
        Esto es necesario al iniciar el AlertEngine para poder auto-resolver
        alertas que fueron generadas antes del último reinicio del servicio.
        """
        try:
            # Obtener todas las alertas activas (no reconocidas)
            active_alerts = self.db.get_alerts(ack=False, limit=1000)
            
            count = 0
            for alert in active_alerts:
                sensor_id = alert.get('sensor_id')
                code = alert.get('code')
                alert_id = alert.get('id')
                
                # Crear cache key según el tipo de alerta
                if sensor_id:
                    # Alerta de sensor (umbral)
                    cache_key = (sensor_id, code)
                else:
                    # Alerta de sistema (dispositivo offline)
                    # Extraer unit_id del código o mensaje si es posible
                    if code == 'DEVICE_OFFLINE':
                        # Intentar extraer unit_id del mensaje
                        message = alert.get('message', '')
                        import re
                        match = re.search(r'Unit (\d+)', message)
                        if match:
                            unit_id = match.group(1)
                            cache_key = (f"device_{unit_id}", code)
                        else:
                            continue  # No podemos identificar el dispositivo
                    else:
                        continue  # Tipo de alerta desconocido
                
                # Registrar en cache
                self._active_alerts_cache[cache_key] = alert_id
                count += 1
            
            if count > 0:
                logger.info(f"📋 Cache de alertas activas reconstruido: {count} alertas cargadas")
        
        except Exception as e:
            logger.error(f"Error al reconstruir cache de alertas activas: {e}", exc_info=True)
    
    
    # ========================================================================
    # CONSULTAS DE ALERTAS
    # ========================================================================
    
    def get_active_alerts(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Obtiene alertas activas (no reconocidas).
        
        Args:
            limit: Número máximo de alertas
        
        Returns:
            Lista de alertas activas
        """
        return self.db.get_alerts(ack=False, limit=limit)
    
    
    def get_alert_stats(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas de alertas.
        
        Returns:
            Dict con estadísticas:
                - total_active: Alertas no reconocidas
                - by_level: Dict con conteo por nivel (INFO, WARN, ALARM, CRITICAL)
                - recent_count: Alertas en última hora
        """
        # Alertas activas
        active = self.db.get_alerts(ack=False, limit=1000)
        
        # Conteo por nivel
        by_level = {
            'INFO': 0,
            'WARN': 0,
            'ALARM': 0,
            'CRITICAL': 0
        }
        
        # Alertas recientes (última hora) - usar naive UTC
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        recent_count = 0
        
        for alert in active:
            # Conteo por nivel
            level = alert.get('level', 'INFO')
            if level in by_level:
                by_level[level] += 1
            
            # Conteo recientes
            try:
                alert_time_str = alert['timestamp'].replace('Z', '+00:00')
                alert_time = datetime.fromisoformat(alert_time_str)
                
                # Convertir a naive UTC si es aware
                if alert_time.tzinfo is not None:
                    alert_time = alert_time.replace(tzinfo=None)
                
                if alert_time > one_hour_ago:
                    recent_count += 1
            except (ValueError, KeyError):
                pass
        
        return {
            'total_active': len(active),
            'by_level': by_level,
            'recent_count': recent_count
        }
    
    
    def acknowledge_alert(self, alert_id: int):
        """
        Reconoce una alerta.
        
        Args:
            alert_id: ID de la alerta
        """
        self.db.acknowledge_alert(alert_id)
        logger.info(f"✅ Alerta {alert_id} reconocida")
        
        # Emitir evento de reconocimiento vía SocketIO
        if self.socketio:
            self.socketio.emit('alert_acknowledged', {'alert_id': alert_id}, namespace='/')
    
    
    def clear_device_alerts(self, unit_id: int):
        """
        Limpia todas las alertas activas de un dispositivo y su caché.
        Se llama cuando un dispositivo se elimina del polling por timeout.
        
        Args:
            unit_id: ID del dispositivo a limpiar
        """
        try:
            # Buscar y auto-reconocer TODAS las alertas del dispositivo
            active_alerts = self.db.get_alerts(ack=False, limit=1000)
            
            resolved_count = 0
            device_prefix = f"UNIT_{unit_id}_"
            
            for alert in active_alerts:
                alert_id = alert.get('id')
                alert_sensor_id = alert.get('sensor_id', '')
                
                # Verificar si la alerta pertenece a este dispositivo
                # Puede ser alerta de sensor (UNIT_X_TILT_Y) o de dispositivo (device_X)
                if (alert_sensor_id and alert_sensor_id.startswith(device_prefix)) or \
                   (alert.get('message', '').find(f"Unit {unit_id}") >= 0):
                    
                    # Auto-reconocer esta alerta
                    self.db.acknowledge_alert(alert_id)
                    resolved_count += 1
                    
                    # Emitir evento de reconocimiento
                    if self.socketio:
                        self.socketio.emit('alert_acknowledged', {
                            'alert_id': alert_id,
                            'auto': True,
                            'reason': f"Dispositivo {unit_id} eliminado del polling por timeout (180s offline)"
                        }, namespace='/')
            
            if resolved_count > 0:
                logger.info(f"✅ {resolved_count} alerta(s) del dispositivo unit_{unit_id} auto-reconocidas")
            
            # Limpiar caché de alertas del dispositivo
            keys_to_remove = [
                key for key in self._active_alerts_cache.keys()
                if key[0].startswith(device_prefix)
            ]
            for key in keys_to_remove:
                del self._active_alerts_cache[key]
            
            # Limpiar caché de última alerta del dispositivo
            keys_to_remove = [
                key for key in self._last_alert_cache.keys()
                if key[0].startswith(device_prefix)
            ]
            for key in keys_to_remove:
                del self._last_alert_cache[key]
            
            logger.info(f"🧹 Alertas del dispositivo unit_{unit_id} limpiadas")
            
        except Exception as e:
            logger.error(f"Error al limpiar alertas del dispositivo {unit_id}: {e}", exc_info=True)

