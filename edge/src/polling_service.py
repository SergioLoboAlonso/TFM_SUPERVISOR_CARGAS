"""
Polling Service: servicio en background para lectura automática de telemetría.
Actualiza dispositivos y emite eventos vía WebSocket.
"""
import threading
import time
from typing import List, Optional, Callable
from datetime import datetime
from modbus_master import ModbusMaster
from device_manager import DeviceManager
from data_normalizer import DataNormalizer
from logger import logger
from config import Config


class PollingService:
    """Servicio de polling automático con thread en background"""
    
    # Direcciones de Input Registers (telemetría)
    IR_TELEMETRY_START = 0x0000
    IR_TELEMETRY_COUNT = 13  # Base (MPU+load)
    MIN_INTERVAL_SEC = 0.2  # Evita saturar el bus/CPU con intervalos demasiado bajos
    
    def __init__(self, modbus_master: ModbusMaster, device_manager: DeviceManager):
        self.modbus = modbus_master
        self.device_mgr = device_manager
        self.normalizer = DataNormalizer()
        
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
                        else:
                            # Aumentar contador y aplicar backoff adaptativo
                            self._consec_errors[unit_id] = self._consec_errors.get(unit_id, 0) + 1
                            base = Config.OFFLINE_BACKOFF_SEC
                            cap = Config.OFFLINE_BACKOFF_MAX_SEC
                            backoff = min(base * (2 ** (self._consec_errors[unit_id] - 1)), cap)
                            self._next_allowed_poll_ts[unit_id] = now + backoff
                            logger.debug(f"unit {unit_id}: error => backoff {backoff:.1f}s (errores={self._consec_errors[unit_id]})")

                        if self.on_telemetry_callback:
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
    
    def _read_telemetry(self, unit_id: int) -> Optional[dict]:
        """
        Lee telemetría de un dispositivo.
        
        Args:
            unit_id: ID del dispositivo
        
        Returns:
            Dict con telemetría normalizada o None si error
        """
        # Determinar cuántos registros leer según capacidades (añadir viento si aplica)
        read_count = self.IR_TELEMETRY_COUNT
        device = self.device_mgr.get_device(unit_id)
        if device and isinstance(device.capabilities, list) and ('Wind' in device.capabilities):
            read_count += 2  # 0x000D..0x000E: viento (cm/s, dir)

        # Leer Input Registers (0x04)
        raw_regs = self.modbus.read_input_registers(
            unit_id,
            self.IR_TELEMETRY_START,
            read_count,
            retry=True
        )
        
        # DEBUG: Log de registros crudos
        logger.info(f"📊 UnitID {unit_id} raw_regs ({len(raw_regs) if raw_regs else 0}): {raw_regs}")
        
        if not raw_regs or len(raw_regs) < self.IR_TELEMETRY_COUNT:
            logger.warning(f"No se pudo leer telemetría de unit {unit_id}")
            self.device_mgr.update_device_status(unit_id, success=False)
            
            # Emitir evento de error
            device = self.device_mgr.get_device(unit_id)
            return {
                'unit_id': unit_id,
                'alias': device.alias if device else f"Unit {unit_id}",
                'timestamp': datetime.now().isoformat(),
                'status': 'error',
                'error': 'timeout_or_crc_error'
            }
        
        # Normalizar datos
        try:
            telemetry = self.normalizer.normalize_telemetry(raw_regs)
            # Si hay datos de viento (registros 13 y 14), añadir campos normalizados
            if len(raw_regs) >= self.IR_TELEMETRY_COUNT + 2:
                try:
                    wind_speed_mps = raw_regs[13] / 100.0
                    wind_dir_deg = raw_regs[14]
                    telemetry['wind_speed_mps'] = wind_speed_mps
                    telemetry['wind_direction_deg'] = wind_dir_deg
                except Exception as _:
                    pass
            
            # Obtener info del dispositivo
            device = self.device_mgr.get_device(unit_id)
            self.device_mgr.update_device_status(unit_id, success=True)
            
            # Construir payload completo
            return {
                'unit_id': unit_id,
                'alias': device.alias if device else f"Unit {unit_id}",
                'timestamp': datetime.now().isoformat(),
                'telemetry': telemetry,
                'status': 'ok'
            }
        
        except Exception as e:
            logger.error(f"Error al normalizar telemetría de unit {unit_id}: {e}")
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
