"""
Device Manager: gestión de dispositivos Modbus, discovery, caché de identidad.
"""
from typing import Dict, Optional, List
from datetime import datetime
import time
from modbus_master import ModbusMaster
from data_normalizer import DataNormalizer
from logger import logger


class Device:
    """Modelo de dispositivo con identidad y estado"""
    
    def __init__(self, unit_id: int):
        self.unit_id = unit_id
        
        # Identidad (leída de registros)
        self.vendor_id = None
        self.product_id = None
        self.vendor_str = ""
        self.product_str = ""
        self.hw_version = ""
        self.fw_version = ""
        self.alias = ""
        self.capabilities = []
        self.identify_info = None  # Info ASCII de función 0x41
        
        # Estado
        self.status = "unknown"  # "online", "offline", "degraded"
        self.last_seen = None
        self.consecutive_errors = 0
        
        # Estadísticas
        self.uptime_sec = 0
        self.status_flags = []
        self.error_flags = []
    
    def to_dict(self) -> dict:
        """Serializa a diccionario para API REST"""
        return {
            'unit_id': self.unit_id,
            'vendor_id': f"0x{self.vendor_id:04X}" if self.vendor_id else None,
            'product_id': f"0x{self.product_id:04X}" if self.product_id else None,
            'vendor': self.vendor_str,
            'product': self.product_str,
            'hw_version': self.hw_version,
            'fw_version': self.fw_version,
            'alias': self.alias,
            'capabilities': self.capabilities,
            'status': self.status,
            'last_seen': self.last_seen.isoformat() if self.last_seen else None,
            'uptime_sec': self.uptime_sec,
            'status_flags': self.status_flags,
            'error_flags': self.error_flags,
            'identify_info': self.identify_info
        }


class DeviceManager:
    """Gestión de dispositivos: discovery, identidad, alias, comandos"""
    
    # Mapa de registros Modbus (conforme a registersModbus.h del firmware)
    # Holding Registers (HR)
    HR_INFO_VENDOR_ID = 0x0000
    HR_INFO_PRODUCTO_ID = 0x0001
    HR_INFO_VERSION_HW = 0x0002
    HR_INFO_VERSION_FW = 0x0003
    HR_INFO_CAPACIDADES = 0x0005
    HR_INFO_UPTIME_S_LO = 0x0006
    HR_INFO_UPTIME_S_HI = 0x0007
    HR_INFO_ESTADO = 0x0008
    HR_INFO_ERRORES = 0x0009
    
    # Config
    HR_CFG_ID_UNIDAD = 0x0014
    HR_CMD_GUARDAR = 0x0012
    HR_CMD_IDENT_SEGUNDOS = 0x0013
    
    # Identidad extendida
    HR_INFO_VENDOR_STR_LEN = 0x0026
    HR_INFO_VENDOR_STR0 = 0x0027
    HR_INFO_PRODUCT_STR_LEN = 0x002B
    HR_INFO_PRODUCT_STR0 = 0x002C
    
    # Alias
    HR_ID_ALIAS_LEN = 0x0030
    HR_ID_ALIAS0 = 0x0031
    
    # Input Registers (IR)
    IR_MED_ANGULO_X_CDEG = 0x0000
    IR_MED_ANGULO_Y_CDEG = 0x0001
    IR_MED_TEMPERATURA_CENTI = 0x0002
    IR_MED_ACEL_X_mG = 0x0003
    IR_MED_PESO_KG = 0x000C
    
    def __init__(self, modbus_master: ModbusMaster, normalizer: DataNormalizer):
        """
        Inicializa DeviceManager.
        
        Args:
            modbus_master: Instancia de ModbusMaster para comunicación RS-485
            normalizer: Instancia de DataNormalizer para conversión de datos
        """
        self.modbus = modbus_master
        self.normalizer = normalizer
        self.normalizer = normalizer
        self.devices: Dict[int, Device] = {}  # {unit_id: Device}
    
    def discover_devices(self, unit_id_min: int = 1, unit_id_max: int = 10,
                        discovery_timeout: float = None, 
                        progress_callback=None) -> List[Device]:
        """
        Descubre dispositivos en el bus escaneando rango de UnitIDs.
        
        Args:
            unit_id_min: UnitID inicial (1..247)
            unit_id_max: UnitID final (1..247)
            discovery_timeout: Timeout reducido para discovery rápido (default: Config.MODBUS_DISCOVERY_TIMEOUT)
            progress_callback: Función callback(current, total, unit_id) para reportar progreso
        
        Returns:
            Lista de dispositivos encontrados
        """
        import time as timing
        from config import Config
        if discovery_timeout is None:
            discovery_timeout = Config.MODBUS_DISCOVERY_TIMEOUT
        
        # Guardar timeout original y reducir temporalmente
        original_timeout = self.modbus.timeout
        
        # pymodbus 3.x: timeout está en comm_params
        if hasattr(self.modbus.client, 'comm_params'):
            logger.info(f"Timeout ANTES: comm_params.timeout_connect={self.modbus.client.comm_params.timeout_connect}")
            self.modbus.client.comm_params.timeout_connect = discovery_timeout
            logger.info(f"Timeout DESPUÉS: comm_params.timeout_connect={self.modbus.client.comm_params.timeout_connect}")
        else:
            logger.warning("No se pudo cambiar timeout - comm_params no disponible")
        
        total_units = unit_id_max - unit_id_min + 1
        logger.info(f"Iniciando discovery: UnitID {unit_id_min}..{unit_id_max} (timeout={discovery_timeout}s)")
        found_devices = []
        
        discovery_start = timing.time()
        
        for idx, unit_id in enumerate(range(unit_id_min, unit_id_max + 1), start=1):
            unit_start = timing.time()
            
            # Reportar progreso
            if progress_callback:
                try:
                    progress_callback(idx, total_units, unit_id)
                except Exception as e:
                    logger.warning(f"Error en progress_callback: {e}")
            
            try:
                # Leer vendor_id como probe (1 registro)
                result = self.modbus.read_holding_registers(unit_id, self.HR_INFO_VENDOR_ID, 1, retry=False)
                
                elapsed = timing.time() - unit_start
                if result and len(result) >= 1:
                    logger.info(f"✅ UnitID {unit_id} respondió en {elapsed:.3f}s, Vendor=0x{result[0]:04X}")
                    
                    # Leer identidad completa
                    device = self._read_device_identity(unit_id)
                    if device:
                        self.devices[unit_id] = device
                        found_devices.append(device)
                    
                    # Sin delay después de encontrar dispositivo - el timeout de pymodbus ya da margen suficiente
                else:
                    logger.debug(f"⏱️ UnitID {unit_id} sin respuesta en {elapsed:.3f}s")
            
            except Exception as e:
                elapsed = timing.time() - unit_start
                logger.debug(f"⏱️ UnitID {unit_id}: error en {elapsed:.3f}s ({e})")
                continue
        
        # Restaurar timeout original
        if hasattr(self.modbus.client, 'comm_params'):
            self.modbus.client.comm_params.timeout_connect = original_timeout
            logger.info(f"Timeout RESTAURADO: comm_params.timeout_connect={self.modbus.client.comm_params.timeout_connect}")
        
        total_time = timing.time() - discovery_start
        scan_count = unit_id_max - unit_id_min + 1
        avg_time_per_unit = total_time / scan_count if scan_count > 0 else 0
        
        logger.info(f"Discovery completado en {total_time:.2f}s: {len(found_devices)} dispositivos encontrados")
        logger.info(f"📊 Estadísticas: {scan_count} UnitIDs escaneados @ {avg_time_per_unit*1000:.0f}ms/unit (timeout={discovery_timeout*1000:.0f}ms)")
        logger.info(f"📊 Overhead: {(avg_time_per_unit/discovery_timeout - 1)*100:.0f}% sobre timeout teórico")
        
        return found_devices
    
    def _read_device_identity(self, unit_id: int) -> Optional[Device]:
        """
        Lee identidad completa de un dispositivo.
        
        Args:
            unit_id: ID del dispositivo
        
        Returns:
            Device con identidad o None si error
        """
        device = Device(unit_id)
        
        try:
            # Leer bloque de info (0x0000..0x0009 = 10 registros)
            info_regs = self.modbus.read_holding_registers(unit_id, self.HR_INFO_VENDOR_ID, 10)
            if not info_regs or len(info_regs) < 10:
                logger.error(f"No se pudo leer info de unit {unit_id}")
                return None
            
            # Parsear info
            device.vendor_id = info_regs[0]
            device.product_id = info_regs[1]
            device.vendor_str, device.product_str = self.normalizer.decode_vendor_product(
                device.vendor_id, device.product_id
            )
            device.hw_version = self.normalizer.decode_version(info_regs[2])
            device.fw_version = self.normalizer.decode_version(info_regs[3])
            device.capabilities = self.normalizer.decode_capabilities(info_regs[5])
            
            # Uptime (32-bit)
            uptime_lo = info_regs[6]
            uptime_hi = info_regs[7]
            device.uptime_sec = (uptime_hi << 16) | uptime_lo
            
            # Estado y errores
            device.status_flags = self.normalizer.decode_status_flags(info_regs[8])
            device.error_flags = self.normalizer.decode_error_flags(info_regs[9])
            
            # Leer alias (0x0030 = len, 0x0031..0x0050 = data)
            alias_header = self.modbus.read_holding_registers(unit_id, self.HR_ID_ALIAS_LEN, 1)
            if alias_header and len(alias_header) >= 1:
                alias_len = alias_header[0]
                if alias_len > 0 and alias_len <= 64:
                    # Leer registros de alias (máx 32 regs para 64 bytes)
                    regs_needed = (alias_len + 1) // 2
                    alias_regs = self.modbus.read_holding_registers(unit_id, self.HR_ID_ALIAS0, regs_needed)
                    if alias_regs:
                        device.alias = self.normalizer.decode_alias(alias_len, alias_regs)
            
            # Marcar como online
            device.status = "online"
            device.last_seen = datetime.now()
            device.consecutive_errors = 0
            
            return device
        
        except Exception as e:
            logger.error(f"Error al leer identidad de unit {unit_id}: {e}")
            return None
    
    def get_device(self, unit_id: int) -> Optional[Device]:
        """Retorna dispositivo desde caché"""
        return self.devices.get(unit_id)
    
    def get_all_devices(self) -> List[Device]:
        """Retorna lista de todos los dispositivos en caché"""
        return list(self.devices.values())
    
    def update_device_status(self, unit_id: int, success: bool):
        """
        Actualiza estado de dispositivo tras operación Modbus.
        
        Args:
            unit_id: ID del dispositivo
            success: True si operación exitosa, False si error
        """
        device = self.devices.get(unit_id)
        if not device:
            return
        
        if success:
            device.status = "online"
            device.last_seen = datetime.now()
            device.consecutive_errors = 0
        else:
            device.consecutive_errors += 1
            
            if device.consecutive_errors >= 3:
                device.status = "offline"
                logger.warning(f"Dispositivo {unit_id} marcado como offline (3+ errores consecutivos)")
            elif device.consecutive_errors >= 1:
                device.status = "degraded"
    
    def identify_device(self, unit_id: int, duration_sec: int = 10) -> dict:
        """
        Activa LED de identificación en dispositivo usando función propietaria 0x41.
        
        NOTA: El firmware ignora el parámetro duration_sec y usa IDENTIFY_DEFAULT_SECS (5s).
        La función 0x41 activa automáticamente el Identify y retorna información del dispositivo.
        
        Args:
            unit_id: ID del dispositivo
            duration_sec: Duración deseada (IGNORADO por firmware, siempre usa 5s)
        
        Returns:
            Dict con {success: bool, info: str} donde info contiene la respuesta ASCII del dispositivo
        """
        logger.info(f"Identificando dispositivo {unit_id} con función 0x41 (LED ~5s)")
        
        # Enviar función propietaria 0x41
        info = self.modbus.send_identify_0x41(unit_id)
        
        if info:
            logger.info(f"✅ Identify activado en unit {unit_id}: {info[:60]}")
            self.update_device_status(unit_id, True)
            
            # Guardar la info en el dispositivo para acceso posterior
            if unit_id in self.devices:
                self.devices[unit_id].identify_info = info
            
            return {'success': True, 'info': info}
        else:
            logger.error(f"Error al enviar comando Identify 0x41 a unit {unit_id}")
            self.update_device_status(unit_id, False)
            return {'success': False, 'info': None}
    
    def write_alias_to_ram(self, unit_id: int, alias: str) -> bool:
        """
        Escribe alias a dispositivo (solo RAM, NO persiste en EEPROM).
        
        Args:
            unit_id: ID del dispositivo
            alias: Nuevo alias (máx 64 caracteres ASCII)
        
        Returns:
            True si escrito exitosamente
        """
        logger.info(f"Escribiendo alias '{alias}' en RAM del dispositivo {unit_id}")
        
        # Validar alias
        if len(alias) > 64:
            logger.error(f"Alias demasiado largo: {len(alias)} caracteres (máx 64)")
            return False
        
        # Codificar alias
        alias_len, alias_regs = self.normalizer.encode_alias(alias)
        
        # Construir trama Write Multiple: [len, reg0, reg1, ...]
        data_regs = [alias_len] + alias_regs
        
        # DEBUG: Log detallado
        logger.info(f"📝 Alias encode: len={alias_len}, regs_count={len(alias_regs)}, total_regs={len(data_regs)}")
        logger.info(f"📝 Data to write: addr=0x{self.HR_ID_ALIAS_LEN:04X} ({self.HR_ID_ALIAS_LEN}), count={len(data_regs)}")
        logger.info(f"📝 First 5 values: {data_regs[:5]}")
        
        # Escribir con función 0x10 (Write Multiple Registers)
        success = self.modbus.write_registers(unit_id, self.HR_ID_ALIAS_LEN, data_regs)
        if not success:
            logger.error(f"Error al escribir alias en unit {unit_id}")
            self.update_device_status(unit_id, False)
            return False
        
        # Actualizar caché local
        device = self.devices.get(unit_id)
        if device:
            device.alias = alias
        
        self.update_device_status(unit_id, True)
        logger.info(f"✅ Alias escrito en RAM de unit {unit_id}")
        return True
    
    def write_unit_id_to_ram(self, current_unit_id: int, new_unit_id: int) -> bool:
        """
        Cambia Unit ID del dispositivo (solo RAM, NO persiste en EEPROM).
        
        Args:
            current_unit_id: ID actual del dispositivo
            new_unit_id: Nuevo ID (1-247)
        
        Returns:
            True si cambiado exitosamente
        """
        logger.info(f"Cambiando UnitID de {current_unit_id} a {new_unit_id} (RAM)")
        
        if not (1 <= new_unit_id <= 247):
            logger.error(f"UnitID inválido: {new_unit_id} (debe ser 1..247)")
            return False
        
        success = self.modbus.write_register(current_unit_id, self.HR_CFG_ID_UNIDAD, new_unit_id)
        if not success:
            logger.error(f"Error al cambiar UnitID en dispositivo {current_unit_id}")
            self.update_device_status(current_unit_id, False)
            return False
        
        # Mover dispositivo en caché
        device = self.devices.pop(current_unit_id, None)
        if device:
            device.unit_id = new_unit_id
            self.devices[new_unit_id] = device
        
        self.update_device_status(new_unit_id, True)
        logger.info(f"✅ UnitID cambiado de {current_unit_id} a {new_unit_id} (RAM)")
        return True
    
    def save_to_eeprom(self, unit_id: int) -> bool:
        """
        Envía comando SAVE (0xA55A) para persistir configuración actual en EEPROM.
        
        Args:
            unit_id: ID del dispositivo
        
        Returns:
            True si comando enviado exitosamente
        """
        logger.info(f"Guardando configuración en EEPROM del dispositivo {unit_id}")
        
        success = self.modbus.write_register(unit_id, self.HR_CMD_GUARDAR, 0xA55A)
        if not success:
            logger.error(f"Error al enviar comando SAVE a unit {unit_id}")
            self.update_device_status(unit_id, False)
            return False
        
        self.update_device_status(unit_id, True)
        logger.info(f"✅ Comando SAVE (EEPROM) enviado exitosamente a unit {unit_id}")
        return True
    
    def save_alias(self, unit_id: int, alias: str) -> bool:
        """
        DEPRECADO: Usa write_alias_to_ram() + save_to_eeprom() en su lugar.
        
        Escribe alias y guarda en EEPROM en una sola operación.
        """
        if not self.write_alias_to_ram(unit_id, alias):
            return False
        
        time.sleep(0.05)  # Pausa inter-frame
        return self.save_to_eeprom(unit_id)
    
    def change_unit_id(self, old_unit_id: int, new_unit_id: int) -> bool:
        """
        Cambia el Unit ID de un dispositivo.
        
        Args:
            old_unit_id: UnitID actual
            new_unit_id: Nuevo UnitID (1..247)
        
        Returns:
            True si cambio exitoso
        """
        logger.info(f"Cambiando UnitID {old_unit_id} → {new_unit_id}")
        
        # Validar nuevo UnitID
        if new_unit_id < 1 or new_unit_id > 247:
            logger.error(f"UnitID inválido: {new_unit_id} (debe ser 1..247)")
            return False
        
        # Verificar colisión
        if new_unit_id in self.devices and new_unit_id != old_unit_id:
            logger.error(f"UnitID {new_unit_id} ya existe en caché")
            return False
        
        # Escribir nuevo UnitID
        success = self.modbus.write_register(old_unit_id, self.HR_CFG_ID_UNIDAD, new_unit_id)
        if not success:
            logger.error(f"Error al escribir nuevo UnitID en dispositivo {old_unit_id}")
            self.update_device_status(old_unit_id, False)
            return False
        
        # Guardar a EEPROM
        time.sleep(0.05)
        save_success = self.modbus.write_register(old_unit_id, self.HR_CMD_GUARDAR, 0xA55A)
        if not save_success:
            logger.error("Error al guardar nuevo UnitID en EEPROM")
            self.update_device_status(old_unit_id, False)
            return False
        
        # Actualizar caché: mover dispositivo a nueva key
        device = self.devices.pop(old_unit_id, None)
        if device:
            device.unit_id = new_unit_id
            self.devices[new_unit_id] = device
            logger.info(f"Caché actualizada: UnitID {old_unit_id} → {new_unit_id}")
        
        self.update_device_status(new_unit_id, True)
        return True
