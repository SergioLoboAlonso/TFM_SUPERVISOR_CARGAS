"""
============================================================================
POLLING SERVICE - Muestreo Automático de Telemetría
============================================================================

Responsabilidades:
    1. Thread background para lectura continua de dispositivos
    2. Estrategia round-robin para distribución equitativa
    3. Backoff adaptativo para dispositivos offline
    4. Emisión de eventos WebSocket en tiempo real
    5. Lectura selectiva según capacidades del dispositivo

Arquitectura del Polling:
    
    PollingService (thread)
        │
        ├── Tick cada ~200ms (ajustable según num dispositivos)
        │
        ├── Round-robin: selecciona 1 dispositivo por tick
        │      cursor = (cursor + 1) % len(devices)
        │
        ├── Lectura Modbus (estrategia según capacidades):
        │      • Wind-only: 9 regs (0x0009-0x0011)
        │      • MPU-only: 13 regs (0x0000-0x000C)
        │      • Both: 27 regs (0x0000-0x001A)
        │
        ├── Normalización (DataNormalizer)
        │
        ├── Emisión WebSocket
        │      on_telemetry_callback(data)
        │
        └── Backoff adaptativo en errores:
               1er error: 5s, 2do: 10s, 3ro: 20s, ... max 60s

Estrategia de Backoff:
    - Evita saturar dispositivos offline con peticiones continuas
    - Exponencial con cap: 5s, 10s, 20s, 40s, 60s (máximo)
    - Reset automático al recibir respuesta exitosa

============================================================================
"""
import threading
import time
from typing import List, Optional, Callable
from datetime import datetime
from modbus_master import ModbusMaster
from device_manager import DeviceManager
from data_normalizer import DataNormalizer
from database import Database
from logger import logger
from config import Config
from alert_engine import AlertEngine


class PollingService:
    """Servicio de polling automático con thread en background"""
    
    # Direcciones de Input Registers (telemetría)
    IR_TELEMETRY_START = 0x0000
    IR_TELEMETRY_COUNT = 13  # Base (MPU+load)
    # Extensiones:
    # +2 viento actual (speed, direction)
    # +3 estadísticas viento (min/max/avg)
    # +9 estadísticas aceleración (x/y/z min/max/avg)
    IR_TOTAL_WITH_WIND_AND_STATS = 13 + 2 + 3 + 9  # 27
    MIN_INTERVAL_SEC = 0.2  # Evita saturar el bus/CPU con intervalos demasiado bajos
    
    def __init__(self, modbus_master: ModbusMaster, device_manager: DeviceManager, database: Database = None, alert_engine: AlertEngine = None, mqtt_bridge=None):
        self.modbus = modbus_master
        self.device_mgr = device_manager
        self.normalizer = DataNormalizer()
        self.db = database  # Base de datos para persistencia
        self.alert_engine = alert_engine  # Motor de alertas
        self.mqtt_bridge = mqtt_bridge  # Puente MQTT para IoT platforms

        # Cache último paquete de telemetría por unit_id
        self._last_telemetry: dict[int, dict] = {}
        
        # Estado del polling
        self._active = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # Configuración
        self.interval_sec = Config.POLL_INTERVAL_SEC
        self.per_device_refresh_sec = Config.PER_DEVICE_REFRESH_SEC
        self.unit_ids: List[int] = []
        self._cursor = 0
        self._next_allowed_poll_ts = {}
        
        # Callbacks para emitir datos vía WebSocket
        self.on_telemetry_callback: Optional[Callable] = None
        self.on_diagnostic_callback: Optional[Callable] = None
        
        # Contadores para diagnósticos/ticks
        self._tick_counter = 0
        self._diag_every_ticks = 10
        self._consec_errors = {}
        
        logger.info("PollingService inicializado")
    
    def start(self, unit_ids: List[int], interval_sec: float = None, per_device_refresh_sec: float = None):
        """
        Inicia el polling automático.
        
        Args:
            unit_ids: Lista de UnitIDs a monitorear
            interval_sec: Intervalo de polling (si None, usa Config.POLL_INTERVAL_SEC)
        """
        if self._active:
            logger.warning("Polling ya está activo")
            return
        
        if not unit_ids:
            logger.error("No se especificaron dispositivos para polling")
            return
        
        # Limitar número de dispositivos
        if len(unit_ids) > Config.MAX_POLL_DEVICES:
            logger.warning(
                f"Se solicitaron {len(unit_ids)} dispositivos; se limitará a {Config.MAX_POLL_DEVICES} para evitar timeouts"
            )
            unit_ids = unit_ids[:Config.MAX_POLL_DEVICES]
        self.unit_ids = unit_ids
        if interval_sec is not None:
            # Asegurar un intervalo mínimo para evitar timeouts por saturación
            if interval_sec < self.MIN_INTERVAL_SEC:
                logger.warning(
                    f"Intervalo solicitado {interval_sec}s es demasiado bajo; "
                    f"se fuerza a mínimo seguro {self.MIN_INTERVAL_SEC}s"
                )
                self.interval_sec = self.MIN_INTERVAL_SEC
            else:
                self.interval_sec = interval_sec

        if per_device_refresh_sec is not None:
            if per_device_refresh_sec < self.MIN_INTERVAL_SEC:
                logger.warning(
                    f"Refresco por dispositivo {per_device_refresh_sec}s demasiado bajo; se fuerza a mínimo {self.MIN_INTERVAL_SEC}s"
                )
                self.per_device_refresh_sec = self.MIN_INTERVAL_SEC
            else:
                self.per_device_refresh_sec = per_device_refresh_sec
        
        # Asegurar que los dispositivos existen en caché (crea entradas básicas si no)
        for unit_id in unit_ids:
            if not self.device_mgr.get_device(unit_id):
                logger.info(f"Dispositivo {unit_id} no en caché, creando entrada básica")
                from device_manager import Device
                device = Device(unit_id)
                device.status = "online"
                device.last_seen = datetime.now()
                self.device_mgr.devices[unit_id] = device
        
        # Inicializar planificador
        self._cursor = 0
        self._next_allowed_poll_ts = {uid: 0.0 for uid in self.unit_ids}
        self._tick_counter = 0
        self._diag_every_ticks = max(1, 10 * max(1, len(self.unit_ids)))
        self._consec_errors = {uid: 0 for uid in self.unit_ids}

        self._stop_event.clear()
        self._active = True
        
        # Crear thread
        self._thread = threading.Thread(target=self._polling_loop, daemon=True)
        self._thread.start()
        
        logger.info(f"Polling iniciado: UnitIDs={unit_ids}, intervalo={self.interval_sec}s")
    
    def stop(self):
        """Detiene el polling automático"""
        if not self._active:
            return
        
        logger.info("Deteniendo polling...")
        self._active = False
        self._stop_event.set()
        
        if self._thread:
            self._thread.join(timeout=5.0)
            self._thread = None
        
        logger.info("Polling detenido")
    
    def is_active(self) -> bool:
        """Retorna si el polling está activo"""
        return self._active
    
    def get_status(self) -> dict:
        """Retorna estado del polling"""
        return {
            'active': self._active,
            'interval_sec': self.interval_sec,
            'per_device_refresh_sec': self.per_device_refresh_sec,
            'tick_interval_sec': (max(self.MIN_INTERVAL_SEC, self.per_device_refresh_sec / max(1, len(self.unit_ids))) if self.unit_ids else None),
            'unit_ids': self.unit_ids,
            'devices_monitored': len(self.unit_ids)
        }
    
    def _polling_loop(self):
        """Bucle principal de polling (ejecuta en thread)"""
        logger.info("Entrando en bucle de polling...")
        
        while not self._stop_event.is_set():
            tick_start = time.time()

            if not self.unit_ids:
                self._stop_event.wait(timeout=self.MIN_INTERVAL_SEC)
                continue

            # Round-robin: un dispositivo por tick
            unit_id = self.unit_ids[self._cursor]
            self._cursor = (self._cursor + 1) % len(self.unit_ids)

            now = time.time()
            next_allowed = self._next_allowed_poll_ts.get(unit_id, 0.0)
            if now < next_allowed:
                logger.debug(f"Backoff activo unit {unit_id}, próximo intento en {next_allowed - now:.2f}s")
            else:
                try:
                    # Elevar temporalmente el timeout si hay errores consecutivos
                    errors = self._consec_errors.get(unit_id, 0)
                    old_timeout = getattr(self.modbus.client, 'timeout', None)
                    if old_timeout is not None and errors > 0:
                        # Escalar timeout hasta ~1.2s máx
                        new_timeout = min(Config.MODBUS_TIMEOUT * (2 ** min(errors, 3)), 1.2)
                        self.modbus.client.timeout = new_timeout
                        logger.debug(f"unit {unit_id}: timeout escalado a {new_timeout:.2f}s por {errors} errores")

                    telemetry_data = self._read_telemetry(unit_id)

                    if telemetry_data:
                        if telemetry_data.get('status') == 'ok':
                            self._next_allowed_poll_ts[unit_id] = 0.0
                            self._consec_errors[unit_id] = 0
                            # Guardar último paquete
                            self._last_telemetry[unit_id] = telemetry_data
                            
                            # Actualizar last_seen del dispositivo
                            if self.db:
                                self.db.update_device_last_seen(unit_id)
                            
                            # Guardar en BD si está disponible
                            if self.db:
                                self._save_to_database(telemetry_data)
                        else:
                            # Aumentar contador y aplicar backoff adaptativo
                            self._consec_errors[unit_id] = self._consec_errors.get(unit_id, 0) + 1
                            base = Config.OFFLINE_BACKOFF_SEC
                            cap = Config.OFFLINE_BACKOFF_MAX_SEC
                            backoff = min(base * (2 ** (self._consec_errors[unit_id] - 1)), cap)
                            self._next_allowed_poll_ts[unit_id] = now + backoff
                            logger.debug(f"unit {unit_id}: error => backoff {backoff:.1f}s (errores={self._consec_errors[unit_id]})")

                        if self.on_telemetry_callback:
                            logger.info(f"🔔 Llamando callback telemetría para unit {unit_id}, status={telemetry_data.get('status')}")
                            self.on_telemetry_callback(telemetry_data)

                    # Diagnósticos aproximados cada 10s por dispositivo
                    self._tick_counter += 1
                    if (self._tick_counter % self._diag_every_ticks) == 0:
                        diagnostic_data = self._read_diagnostic(unit_id)
                        if diagnostic_data and self.on_diagnostic_callback:
                            self.on_diagnostic_callback(diagnostic_data)

                    time.sleep(Config.INTER_FRAME_DELAY_MS / 1000.0)

                except Exception as e:
                    logger.error(f"Error al leer datos de unit {unit_id}: {e}")
                    self._consec_errors[unit_id] = self._consec_errors.get(unit_id, 0) + 1
                    base = Config.OFFLINE_BACKOFF_SEC
                    cap = Config.OFFLINE_BACKOFF_MAX_SEC
                    backoff = min(base * (2 ** (self._consec_errors[unit_id] - 1)), cap)
                    self._next_allowed_poll_ts[unit_id] = time.time() + backoff
                    logger.debug(f"unit {unit_id}: excepción => backoff {backoff:.1f}s (errores={self._consec_errors[unit_id]})")
                finally:
                    # Restaurar timeout original si fue modificado
                    if old_timeout is not None and errors > 0:
                        self.modbus.client.timeout = old_timeout

            # Mantener objetivo de 1s por dispositivo ⇒ tick ≈ 1/len(unit_ids)
            target_tick = max(self.MIN_INTERVAL_SEC, self.per_device_refresh_sec / max(1, len(self.unit_ids)))
            elapsed = time.time() - tick_start
            sleep_time = max(0.0, target_tick - elapsed)
            if sleep_time > 0:
                self._stop_event.wait(timeout=sleep_time)
        
        logger.info("Saliendo del bucle de polling")
    
    def get_last_wind(self, unit_id: int) -> Optional[dict]:
        """Retorna último paquete de viento para unit_id (o None si no hay)."""
        data = self._last_telemetry.get(unit_id)
        if not data or data.get('status') != 'ok':
            return None
        telem = data.get('telemetry', {})
        if 'wind_speed_mps' not in telem:
            return None
        return {
            'unit_id': unit_id,
            'wind_speed_mps': telem.get('wind_speed_mps'),
            'wind_speed_kmh': telem.get('wind_speed_kmh'),
            'wind_direction_deg': telem.get('wind_direction_deg'),
            'timestamp': data.get('timestamp')
        }

    def get_last_stats(self, unit_id: int) -> Optional[dict]:
        """Retorna últimas estadísticas (viento y aceleración) si disponibles."""
        data = self._last_telemetry.get(unit_id)
        if not data or data.get('status') != 'ok':
            return None
        telem = data.get('telemetry', {})
        has_any = ('wind_stats' in telem) or ('acceleration_stats' in telem)
        if not has_any:
            return None
        payload = {
            'unit_id': unit_id,
            'timestamp': data.get('timestamp')
        }
        if 'wind_stats' in telem:
            payload['wind_stats'] = telem['wind_stats']
            if 'wind_speed_kmh' in telem:
                payload['current_wind_kmh'] = telem['wind_speed_kmh']
        if 'acceleration_stats' in telem:
            payload['acceleration_stats'] = telem['acceleration_stats']
        return payload
    
    @staticmethod
    def _to_int16(val: int) -> int:
        """Convierte uint16 a int16 (complemento a 2)"""
        return val if val < 32768 else val - 65536
    
    def _read_telemetry(self, unit_id: int) -> Optional[dict]:
        """
        Lee telemetría de un dispositivo.
        
        Args:
            unit_id: ID del dispositivo
        
        Returns:
            Dict con telemetría normalizada o None si error
        """
        # Seleccionar estrategia de lectura según capacidades
        device = self.device_mgr.get_device(unit_id)
        caps = set(device.capabilities) if device and isinstance(device.capabilities, list) else set()
        has_wind = 'Wind' in caps
        has_mpu = 'MPU6050' in caps
        has_load = 'Load' in caps

        # Utilidades locales
        def to_uint32(lo: int, hi: int) -> int:
            return ((hi & 0xFFFF) << 16) | (lo & 0xFFFF)

        try:
            # Caso 1: solo Load (sin MPU ni Wind) → OPTIMIZADO: leer solo 4 registros necesarios
            # IR[9-10]: sample_count (LSW+MSW), IR[11]: quality_flags, IR[12]: load_kg
            if has_load and not has_mpu and not has_wind:
                raw_regs = self.modbus.read_input_registers(unit_id, 0x0009, 4, retry=True)
                logger.info(f"📊 UnitID {unit_id} load-only raw (4 regs @0x0009): {raw_regs}")

                if not raw_regs or len(raw_regs) < 4:
                    logger.warning(f"No se pudo leer telemetría (load-only) de unit {unit_id}")
                    self.device_mgr.update_device_status(unit_id, success=False)
                    return {
                        'unit_id': unit_id,
                        'alias': device.alias if device else f"Unit {unit_id}",
                        'timestamp': datetime.now().isoformat(),
                        'status': 'error',
                        'error': 'timeout_or_crc_error'
                    }

                # Construir telemetría manualmente (más eficiente que llamar al normalizer con array parcial)
                telemetry = {
                    'sample_count': to_uint32(raw_regs[0], raw_regs[1]),
                    'quality_flags': raw_regs[2],
                    'load_g': self._to_int16(raw_regs[3]) * 10.0,  # ckg → gramos
                    'load_kg': self._to_int16(raw_regs[3]) / 100.0  # ckg → kg
                }
                logger.info(
                    f"⚖️ unit {unit_id} load-only: {telemetry['load_g']:.2f}g, samples={telemetry['sample_count']}"
                )
                self.device_mgr.update_device_status(unit_id, success=True)
                return {
                    'unit_id': unit_id,
                    'alias': device.alias if device else f"Unit {unit_id}",
                    'timestamp': datetime.now().isoformat(),
                    'telemetry': telemetry,
                    'status': 'ok'
                }

            # Caso 2: solo viento → ampliar ventana para incluir estadísticas (0x0009..0x0011 ⇒ 9 registros)
            if has_wind and not has_mpu:
                regs = self.modbus.read_input_registers(unit_id, 0x0009, 9, retry=True)

                logger.info(
                    f"📊 UnitID {unit_id} wind-only raw window (9 regs) @0x0009: {regs}"
                )

                if not regs or len(regs) < 6:  # mínimo para valores actuales
                    logger.warning(f"No se pudo leer telemetría (wind-only) de unit {unit_id}")
                    self.device_mgr.update_device_status(unit_id, success=False)
                    return {
                        'unit_id': unit_id,
                        'alias': device.alias if device else f"Unit {unit_id}",
                        'timestamp': datetime.now().isoformat(),
                        'status': 'error',
                        'error': 'timeout_or_crc_error'
                    }

                wind_speed_mps = regs[4] / 100.0
                telemetry = {
                    'sample_count': to_uint32(regs[0], regs[1]),
                    'wind_speed_mps': wind_speed_mps,
                    'wind_speed_kmh': wind_speed_mps * 3.6,
                    'wind_direction_deg': regs[5]
                }
                if len(regs) >= 9:
                    wind_min_mps = regs[6] / 100.0
                    wind_max_mps = regs[7] / 100.0
                    wind_avg_mps = regs[8] / 100.0
                    telemetry['wind_stats'] = {
                        'min_mps': wind_min_mps,
                        'max_mps': wind_max_mps,
                        'avg_mps': wind_avg_mps,
                        'min_kmh': wind_min_mps * 3.6,
                        'max_kmh': wind_max_mps * 3.6,
                        'avg_kmh': wind_avg_mps * 3.6
                    }

                logger.info(
                    f"🌬️ unit {unit_id} wind-only: speed={telemetry['wind_speed_mps']:.2f} m/s ({telemetry['wind_speed_kmh']:.2f} km/h), dir={telemetry['wind_direction_deg']}°"
                )
                if 'wind_stats' in telemetry:
                    ws = telemetry['wind_stats']
                    logger.info(
                        f"📈 wind stats unit {unit_id}: min={ws['min_mps']:.2f} m/s max={ws['max_mps']:.2f} m/s avg={ws['avg_mps']:.2f} m/s"
                    )

                self.device_mgr.update_device_status(unit_id, success=True)
                return {
                    'unit_id': unit_id,
                    'alias': device.alias if device else f"Unit {unit_id}",
                    'timestamp': datetime.now().isoformat(),
                    'telemetry': telemetry,
                    'status': 'ok'
                }

            # Caso 3: solo MPU (sin Load ni Wind) → leer solo MPU data (12 regs, sin load)
            # O si tiene MPU+Load pero NO Wind → leer 13 regs (todo el bloque base)
            if has_mpu and not has_wind:
                # Si NO tiene Load, solo necesitamos 12 registros (0x0000-0x000B)
                # Si tiene Load, necesitamos 13 registros (0x0000-0x000C)
                count = 13 if has_load else 12
                raw_regs = self.modbus.read_input_registers(unit_id, self.IR_TELEMETRY_START, count, retry=True)
                logger.info(f"📊 UnitID {unit_id} mpu{'+ load' if has_load else ''}-only raw ({len(raw_regs) if raw_regs else 0}/{count}): {raw_regs}")

                if not raw_regs or len(raw_regs) < count:
                    logger.warning(f"No se pudo leer telemetría (mpu-only) de unit {unit_id}")
                    self.device_mgr.update_device_status(unit_id, success=False)
                    return {
                        'unit_id': unit_id,
                        'alias': device.alias if device else f"Unit {unit_id}",
                        'timestamp': datetime.now().isoformat(),
                        'status': 'error',
                        'error': 'timeout_or_crc_error'
                    }

                telemetry = self.normalizer.normalize_telemetry(raw_regs, device.capabilities)
                self.device_mgr.update_device_status(unit_id, success=True)
                return {
                    'unit_id': unit_id,
                    'alias': device.alias if device else f"Unit {unit_id}",
                    'timestamp': datetime.now().isoformat(),
                    'telemetry': telemetry,
                    'status': 'ok'
                }

            # Caso 4: tiene Wind (con o sin MPU/Load) → leer bloque extendido completo (27 regs)
            # Incluye: base(13) + wind(2) + wind_stats(3) + accel_stats(9) = 27 registros
            read_count = self.IR_TOTAL_WITH_WIND_AND_STATS
            raw_regs = self.modbus.read_input_registers(unit_id, self.IR_TELEMETRY_START, read_count, retry=True)
            
            logger.info(f"📊 UnitID {unit_id} with-wind raw ({len(raw_regs) if raw_regs else 0}/{read_count})")

            if not raw_regs or len(raw_regs) < self.IR_TELEMETRY_COUNT:
                logger.warning(f"No se pudo leer telemetría (wind) de unit {unit_id}")
                self.device_mgr.update_device_status(unit_id, success=False)
                return {
                    'unit_id': unit_id,
                    'alias': device.alias if device else f"Unit {unit_id}",
                    'timestamp': datetime.now().isoformat(),
                    'status': 'error',
                    'error': 'timeout_or_crc_error'
                }

            telemetry = self.normalizer.normalize_telemetry(raw_regs, device.capabilities)
            if 'wind_speed_mps' in telemetry:
                logger.info(
                    f"🌬️ unit {unit_id} both: speed={telemetry['wind_speed_mps']:.2f} m/s ({telemetry.get('wind_speed_kmh', 0):.2f} km/h), dir={telemetry.get('wind_direction_deg')}°"
                )
            if 'wind_stats' in telemetry:
                ws = telemetry['wind_stats']
                logger.info(
                    f"📈 wind stats unit {unit_id}: min={ws['min_mps']:.2f} m/s max={ws['max_mps']:.2f} m/s avg={ws['avg_mps']:.2f} m/s"
                )
            if 'acceleration_stats' in telemetry:
                axs = telemetry['acceleration_stats']
                logger.info(
                    "🧪 accel stats unit %d: X(min=%.3f max=%.3f avg=%.3f) Y(min=%.3f max=%.3f avg=%.3f) Z(min=%.3f max=%.3f avg=%.3f)" % (
                        unit_id,
                        axs['x_g']['min'], axs['x_g']['max'], axs['x_g']['avg'],
                        axs['y_g']['min'], axs['y_g']['max'], axs['y_g']['avg'],
                        axs['z_g']['min'], axs['z_g']['max'], axs['z_g']['avg']
                    )
                )

            self.device_mgr.update_device_status(unit_id, success=True)
            return {
                'unit_id': unit_id,
                'alias': device.alias if device else f"Unit {unit_id}",
                'timestamp': datetime.now().isoformat(),
                'telemetry': telemetry,
                'status': 'ok'
            }

        except Exception as e:
            logger.error(f"Error al leer/normalizar telemetría de unit {unit_id}: {e}")
            self.device_mgr.update_device_status(unit_id, success=False)
            return None
    
    def _read_diagnostic(self, unit_id: int) -> Optional[dict]:
        """
        Lee diagnósticos completos de un dispositivo.
        
        Args:
            unit_id: ID del dispositivo
        
        Returns:
            Dict con información de diagnóstico o None si error
        """
        try:
            # Leer info básica
            info = self.modbus.read_device_info(unit_id)
            if not info:
                logger.warning(f"No se pudo leer info de unit {unit_id}")
                return None
            
            # Leer estadísticas Modbus
            diag = self.modbus.read_device_diagnostics(unit_id)
            if not diag:
                logger.warning(f"No se pudo leer diagnósticos de unit {unit_id}")
                return None
            
            # Leer quality flags
            quality_flags = self.modbus.read_quality_flags(unit_id)
            
            # Decodificar bitmasks
            capabilities = self.modbus.decode_capabilities(info['capabilities'])
            status = self.modbus.decode_status(info['status'])
            
            # Obtener device info del manager
            device = self.device_mgr.get_device(unit_id)
            
            # Construir payload completo
            return {
                'unit_id': unit_id,
                'alias': device.alias if device else f"Unit {unit_id}",
                'vendor_id': info['vendor_id'],
                'product_id': info['product_id'],
                'hw_version': info['hw_version'],
                'fw_version': info['fw_version'],
                'uptime_seconds': info['uptime_s'],
                'capabilities': capabilities,
                'status': status,
                'errors': {
                    'bitmask': info['errors'],
                    'active': []
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
                'timestamp': datetime.now().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Error al leer diagnósticos de unit {unit_id}: {e}")
            return None
    
    def _publish_measurement_to_mqtt(self, unit_id: int, sensor_id: str, sensor_type: str, value: float, unit: str, timestamp: str):
        """
        Helper para publicar medida via MQTT bridge.
        
        Args:
            unit_id: ID del dispositivo Modbus
            sensor_id: ID completo del sensor (ej: "UNIT_2_TILT_X")
            sensor_type: Tipo de sensor (tilt, wind, temperature, etc.)
            value: Valor medido
            unit: Unidad de medida
            timestamp: ISO8601 timestamp
        """
        if self.mqtt_bridge:
            device_id = f"unit_{unit_id}"
            self.mqtt_bridge.publish_measurement(
                device_id=device_id,
                sensor_id=sensor_id,
                sensor_type=sensor_type,
                value=value,
                unit=unit,
                timestamp=timestamp,
                quality="GOOD"
            )
    
    
    def _save_to_database(self, telemetry_data: dict):
        """
        Guarda telemetría en la base de datos y publica a MQTT.
        
        Estrategia:
            - Extrae todos los valores numéricos del paquete de telemetría
            - Cada magnitud (angle_x, angle_y, temp, accel_x, wind_speed, etc.) 
              se guarda como una medida separada
            - El sensor_id se construye como "UNIT_{unit_id}_{tipo}"
            - Permite consultas granulares y agregación flexible para ThingsBoard
            - Publica cada medida a MQTT para integración con plataformas IoT
        
        Args:
            telemetry_data: Dict con telemetría desde _read_telemetry()
        """
        if not telemetry_data or telemetry_data.get('status') != 'ok':
            return
        
        try:
            unit_id = telemetry_data['unit_id']
            alias = telemetry_data.get('alias', f"Unit_{unit_id}")
            timestamp = telemetry_data['timestamp']
            telemetry = telemetry_data.get('telemetry', {})
            
            # Obtener capabilities del dispositivo para determinar tipo
            device = self.device_mgr.get_device(unit_id)
            capabilities = set(device.capabilities) if device and device.capabilities else set()
            
            # Determinar tipo principal del sensor
            # Prioridad: MPU6050 > Wind > Load
            if 'MPU6050' in capabilities:
                main_type = 'tilt'
            elif 'Wind' in capabilities:
                main_type = 'wind'
            elif 'Load' in capabilities:
                main_type = 'load'
            else:
                main_type = 'generic'
            
            # MEDIDAS DE INCLINACIÓN (MPU6050)
            if 'angle_x_deg' in telemetry:
                sensor_id = f"UNIT_{unit_id}_TILT_X"
                value = telemetry['angle_x_deg']
                
                self.db.insert_measurement({
                    'sensor_id': sensor_id,
                    'type': 'tilt',
                    'value': value,
                    'unit': 'deg',
                    'quality': 'OK',
                    'timestamp': timestamp
                })
                
                # Publicar a MQTT
                self._publish_measurement_to_mqtt(unit_id, sensor_id, 'tilt', value, 'deg', timestamp)
                
                # Verificar umbrales de alerta
                if self.alert_engine:
                    sensor_info = self.db.get_sensor(sensor_id)
                    if sensor_info:
                        self.alert_engine.check_measurement_thresholds(
                            sensor_id, value, sensor_info
                        )
            
            if 'angle_y_deg' in telemetry:
                sensor_id = f"UNIT_{unit_id}_TILT_Y"
                value = telemetry['angle_y_deg']
                
                self.db.insert_measurement({
                    'sensor_id': sensor_id,
                    'type': 'tilt',
                    'value': value,
                    'unit': 'deg',
                    'quality': 'OK',
                    'timestamp': timestamp
                })
                
                # Publicar a MQTT
                self._publish_measurement_to_mqtt(unit_id, sensor_id, 'tilt', value, 'deg', timestamp)
                
                # Verificar umbrales de alerta
                if self.alert_engine:
                    sensor_info = self.db.get_sensor(sensor_id)
                    if sensor_info:
                        self.alert_engine.check_measurement_thresholds(
                            sensor_id, value, sensor_info
                        )
            
            # TEMPERATURA (MPU6050)
            if 'temperature_c' in telemetry:
                sensor_id = f"UNIT_{unit_id}_TEMP"
                value = telemetry['temperature_c']
                
                self.db.insert_measurement({
                    'sensor_id': sensor_id,
                    'type': 'temperature',
                    'value': value,
                    'unit': 'celsius',
                    'quality': 'OK',
                    'timestamp': timestamp
                })
                
                # Publicar a MQTT
                self._publish_measurement_to_mqtt(unit_id, sensor_id, 'temperature', value, 'celsius', timestamp)
                
                # Verificar umbrales de alerta
                if self.alert_engine:
                    sensor_info = self.db.get_sensor(sensor_id)
                    if sensor_info:
                        self.alert_engine.check_measurement_thresholds(
                            sensor_id, value, sensor_info
                        )
            
            # ACELERACIÓN (MPU6050) - Guardamos la magnitud total
            if 'acceleration' in telemetry:
                accel = telemetry['acceleration']
                # Magnitud vectorial: sqrt(x² + y² + z²)
                import math
                magnitude = math.sqrt(
                    accel.get('x_g', 0)**2 + 
                    accel.get('y_g', 0)**2 + 
                    accel.get('z_g', 0)**2
                )
                self.db.insert_measurement({
                    'sensor_id': f"UNIT_{unit_id}_ACCEL",
                    'type': 'acceleration',
                    'value': magnitude,
                    'unit': 'g',
                    'quality': 'OK',
                    'timestamp': timestamp
                })
                
                # También guardamos componentes individuales para análisis detallado
                for axis, key in [('X', 'x_g'), ('Y', 'y_g'), ('Z', 'z_g')]:
                    if key in accel:
                        self.db.insert_measurement({
                            'sensor_id': f"UNIT_{unit_id}_ACCEL_{axis}",
                            'type': 'acceleration',
                            'value': accel[key],
                            'unit': 'g',
                            'quality': 'OK',
                            'timestamp': timestamp
                        })
            
            # GIROSCOPIO (MPU6050) - Guardamos magnitud de velocidad angular
            if 'gyroscope' in telemetry:
                gyro = telemetry['gyroscope']
                import math
                magnitude = math.sqrt(
                    gyro.get('x_dps', 0)**2 + 
                    gyro.get('y_dps', 0)**2 + 
                    gyro.get('z_dps', 0)**2
                )
                self.db.insert_measurement({
                    'sensor_id': f"UNIT_{unit_id}_GYRO",
                    'type': 'gyroscope',
                    'value': magnitude,
                    'unit': 'dps',
                    'quality': 'OK',
                    'timestamp': timestamp
                })
            
            # VIENTO
            if 'wind_speed_mps' in telemetry:
                sensor_id = f"UNIT_{unit_id}_WIND_SPEED"
                value = telemetry['wind_speed_mps']
                
                self.db.insert_measurement({
                    'sensor_id': sensor_id,
                    'type': 'wind',
                    'value': value,
                    'unit': 'm_s',
                    'quality': 'OK',
                    'timestamp': timestamp
                })
                
                # Publicar a MQTT
                self._publish_measurement_to_mqtt(unit_id, sensor_id, 'wind', value, 'm_s', timestamp)
                
                # Verificar umbrales de alerta
                if self.alert_engine:
                    sensor_info = self.db.get_sensor(sensor_id)
                    if sensor_info:
                        self.alert_engine.check_measurement_thresholds(
                            sensor_id, value, sensor_info
                        )
            
            if 'wind_direction_deg' in telemetry:
                self.db.insert_measurement({
                    'sensor_id': f"UNIT_{unit_id}_WIND_DIR",
                    'type': 'wind',
                    'value': telemetry['wind_direction_deg'],
                    'unit': 'deg',
                    'quality': 'OK',
                    'timestamp': timestamp
                })
            
            # CARGA (HX711)
            if 'load_kg' in telemetry:
                self.db.insert_measurement({
                    'sensor_id': f"UNIT_{unit_id}_LOAD",
                    'type': 'load',
                    'value': telemetry['load_kg'],
                    'unit': 'kg',
                    'quality': 'OK',
                    'timestamp': timestamp
                })
            
            logger.debug(f"💾 Telemetría de unit {unit_id} guardada en BD")
            
        except Exception as e:
            logger.error(f"Error al guardar telemetría en BD: {e}")
