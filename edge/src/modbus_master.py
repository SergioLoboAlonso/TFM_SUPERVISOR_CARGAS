"""
============================================================================
MODBUS RTU MASTER - Capa de Comunicación Serial
============================================================================

Responsabilidades:
    - Cliente Modbus RTU (Maestro que inicia peticiones)
    - Gestión de puerto serie RS-485
    - Lectura/escritura de registros (funciones 0x03, 0x04, 0x06, 0x10)
    - Manejo de timeouts, reintentos y excepciones
    - Estadísticas de comunicación (TX/RX, errores)

Protocolo Modbus RTU:
    - Capa física: RS-485 half-duplex @ 115200 bps
    - Formato: 8 bits, sin paridad, 1 bit de parada (8N1)
    - CRC16 para detección de errores
    - Delimitación por silencio (3.5 caracteres)

Nota Importante:
    El Master mantiene UN SOLO puerto serie abierto.
    NO se reconecta entre dispositivos diferentes.
    Cada trama especifica el UnitID del esclavo destino.

============================================================================
"""
from typing import Optional, List
import time
from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusException
from logger import logger
from config import Config


class ModbusMaster:
    """Modbus RTU Master - Inicia peticiones a dispositivos esclavos"""
    
    def __init__(self, port: Optional[str] = None, baudrate: Optional[int] = None, 
                 timeout: Optional[float] = None):
        """
        Inicializa el Modbus Master (maestro) RTU.
        
        Args:
            port: Puerto serie (ej. /dev/ttyUSB0). Si None, usa Config.MODBUS_PORT
            baudrate: Velocidad (ej. 115200). Si None, usa Config.MODBUS_BAUDRATE
            timeout: Timeout en segundos. Si None, usa Config.MODBUS_TIMEOUT
        """
        self.port = port or Config.MODBUS_PORT
        self.baudrate = baudrate or Config.MODBUS_BAUDRATE
        self.timeout = timeout or Config.MODBUS_TIMEOUT
        
        # pymodbus client (representa el Master)
        self.client = ModbusSerialClient(
            port=self.port,
            baudrate=self.baudrate,
            timeout=self.timeout,
            parity='N',
            stopbits=1,
            bytesize=8
        )
        
        # Estadísticas
        self.stats = {
            'tx_frames': 0,
            'rx_frames': 0,
            'crc_errors': 0,
            'timeouts': 0,
            'exceptions': 0,
            'errors': 0  # Contador genérico de errores
        }
        # Contadores por unidad para diagnósticos finos
        self._timeouts_per_unit = {}
        
        self._connected = False
        logger.info(f"ModbusClient inicializado: {self.port} @ {self.baudrate} bps")
    
    def connect(self) -> bool:
        """
        Conecta al puerto serie.
        
        Returns:
            True si conectó exitosamente
        """
        try:
            if not self.client.connect():
                logger.error(f"No se pudo conectar a {self.port}")
                return False
            
            self._connected = True
            logger.info(f"Conectado a {self.port}")
            return True
        
        except Exception as e:
            logger.error(f"Error al conectar: {e}")
            return False
    
    def disconnect(self):
        """Cierra la conexión serie"""
        if self._connected:
            self.client.close()
            self._connected = False
            logger.info("Desconectado del puerto serie")
    
    def is_connected(self) -> bool:
        """Retorna si está conectado al puerto serie"""
        return self._connected and self.client.connected
    
    def read_holding_registers(self, unit_id: int, address: int, count: int,
                               retry: bool = True) -> Optional[List[int]]:
        """
        Lee holding registers (función 0x03).
        
        En Modbus RTU, el puerto serial permanece abierto y solo cambiamos el UnitID
        en cada trama. NO hay que reconectar entre esclavos diferentes.
        
        Args:
            unit_id: ID del esclavo (1..247)
            address: Dirección inicial del registro
            count: Cantidad de registros a leer
            retry: Si True, reintenta una vez en caso de timeout
            
        Returns:
            Lista de valores (int) o None si error
        """
        import time as timing
        if not self.is_connected():
            logger.error("Modbus Master no conectado")
            return None
        
        try:
            start_time = timing.time()
            self.stats['tx_frames'] += 1
            result = self.client.read_holding_registers(address, count, slave=unit_id)
            elapsed = timing.time() - start_time
            
            if result.isError():
                # Log solo en DEBUG para discovery masivo
                logger.debug(f"⏱️ No response unit={unit_id} addr=0x{address:04X} in {elapsed:.3f}s")
                
                # Reintentar solo si es timeout y retry=True
                if retry and ("Timeout" in str(result) or "No response" in str(result)):
                    self.stats['timeouts'] += 1
                    self._timeouts_per_unit[unit_id] = self._timeouts_per_unit.get(unit_id, 0) + 1
                    time.sleep(0.01)  # Reducido de 50ms a 10ms
                    return self.read_holding_registers(unit_id, address, count, retry=False)
                
                self.stats['exceptions'] += 1
                return None
            
            self.stats['rx_frames'] += 1
            logger.debug(f"⏱️ OK unit={unit_id} addr=0x{address:04X} in {elapsed:.3f}s")
            return result.registers
        
        except ModbusException as e:
            self.stats['exceptions'] += 1
            logger.debug(f"ModbusException unit={unit_id}: {e}")
            return None
        
        except Exception as e:
            logger.error(f"Error inesperado al leer HR: {e}")
            return None
    
    def read_input_registers(self, unit_id: int, address: int, count: int, retry: bool = True):
        """
        Lee input registers (función 0x04).
        En Modbus RTU, el puerto serial permanece abierto; solo cambia el UnitID por trama.
        
        Args:
            unit_id: ID del esclavo (1..247)
            address: Dirección inicial del registro
            count: Cantidad de registros a leer
            retry: Si True, reintenta una vez en caso de timeout
            
        Returns:
            Lista de valores (int) o None si error
        """
        if not self.is_connected():
            logger.error("Modbus Master no conectado")
            return None
        
        try:
            self.stats['tx_frames'] += 1
            result = self.client.read_input_registers(address, count, slave=unit_id)
            
            logger.debug(f"🔍 read_input_registers unit={unit_id} addr=0x{address:04X} count={count}")
            logger.debug(f"   result.isError()={result.isError()}, type={type(result)}")
            
            if result.isError():
                logger.warning(f"❌ No response unit={unit_id} addr=0x{address:04X}: {result}")
                if retry and ("Timeout" in str(result) or "No response" in str(result)):
                    self.stats['timeouts'] += 1
                    self._timeouts_per_unit[unit_id] = self._timeouts_per_unit.get(unit_id, 0) + 1
                    time.sleep(0.01)  # Reducido de 50ms a 10ms
                    return self.read_input_registers(unit_id, address, count, retry=False)
                self.stats['exceptions'] += 1
                return None
            
            self.stats['rx_frames'] += 1
            logger.debug(f"✅ Received {len(result.registers)} registers: {result.registers[:5]}...")
            return result.registers
        
        except ModbusException as e:
            self.stats['exceptions'] += 1
            logger.error(f"ModbusException: {e}")
            return None
        
        except Exception as e:
            logger.error(f"Error inesperado al leer IR: {e}")
            return None
    
    def write_register(self, unit_id: int, address: int, value: int) -> bool:
        """
        Escribe un registro (función 0x06).
        
        Args:
            unit_id: ID del esclavo (1..247)
            address: Dirección del registro
            value: Valor a escribir (0..65535)
            
        Returns:
            True si escritura exitosa
        """
        if not self.is_connected():
            logger.error("Cliente no conectado")
            return False
        
        try:
            self.stats['tx_frames'] += 1
            result = self.client.write_register(address, value, slave=unit_id)
            
            if result.isError():
                self.stats['exceptions'] += 1
                logger.error(f"Modbus exception al escribir reg unit={unit_id} addr={address}: {result}")
                return False
            
            self.stats['rx_frames'] += 1
            logger.info(f"✅ Registro escrito: unit={unit_id} addr=0x{address:04X} value=0x{value:04X}")
            return True
        
        except ModbusException as e:
            self.stats['exceptions'] += 1
            logger.error(f"ModbusException: {e}")
            return False
        
        except Exception as e:
            logger.error(f"Error inesperado al escribir reg: {e}")
            return False
    
    def write_registers(self, unit_id: int, address: int, values: List[int]) -> bool:
        """
        Escribe múltiples registros (función 0x10).
        
        Args:
            unit_id: ID del esclavo (1..247)
            address: Dirección inicial
            values: Lista de valores a escribir
            
        Returns:
            True si escritura exitosa
        """
        if not self.is_connected():
            logger.error("Cliente no conectado")
            return False
        
        try:
            self.stats['tx_frames'] += 1
            result = self.client.write_registers(address, values, slave=unit_id)
            
            if result.isError():
                self.stats['exceptions'] += 1
                logger.error(f"Modbus exception al escribir registros unit={unit_id} addr={address}: {result}")
                return False
            
            self.stats['rx_frames'] += 1
            logger.info(f"✅ Registros escritos: unit={unit_id} addr=0x{address:04X} count={len(values)}")
            return True
        
        except ModbusException as e:
            self.stats['exceptions'] += 1
            logger.error(f"ModbusException: {e}")
            return False
        
        except Exception as e:
            logger.error(f"Error inesperado al escribir registros: {e}")
            return False
    
    def send_identify_0x41(self, unit_id: int) -> Optional[str]:
        """
        Envía función propietaria 0x41 para activar Identify LED y obtener info del dispositivo.
        
        Esta es la forma correcta según el firmware. La función 0x41:
        - Activa automáticamente el LED Identify por IDENTIFY_DEFAULT_SECS (5s)
        - Retorna información ASCII del dispositivo (vendor, product, fw, hw, etc.)
        
        Args:
            unit_id: ID del dispositivo (1-247)
        
        Returns:
            String ASCII con información del dispositivo o None si falla
        """
        if not self.is_connected():
            logger.error("Modbus Master no conectado")
            return None
        
        try:
            # pymodbus no soporta funciones custom, acceder al socket directo
            if not hasattr(self.client, 'socket') or not self.client.socket:
                logger.error("No hay acceso al socket serial")
                return None
            
            # Importar CRC desde utils
            import sys
            import os
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../firmware/lib/utils/src'))
            
            # Calcular CRC16 Modbus manualmente
            def calc_crc16(data: bytes) -> int:
                crc = 0xFFFF
                for byte in data:
                    crc ^= byte
                    for _ in range(8):
                        if crc & 0x0001:
                            crc = (crc >> 1) ^ 0xA001
                        else:
                            crc >>= 1
                return crc
            
            # Construir trama: [UnitID, 0x41, CRC_L, CRC_H]
            frame = bytes([unit_id, 0x41])
            crc = calc_crc16(frame)
            frame += bytes([crc & 0xFF, (crc >> 8) & 0xFF])
            
            logger.debug(f"Enviando 0x41 a unit {unit_id}: {frame.hex()}")
            
            # Limpiar buffer de entrada
            if hasattr(self.client.socket, 'reset_input_buffer'):
                self.client.socket.reset_input_buffer()
            
            # Enviar trama
            self.client.socket.write(frame)
            
            # Esperar respuesta (dar tiempo al esclavo)
            import time
            time.sleep(0.15)
            
            # Leer respuesta
            if hasattr(self.client.socket, 'in_waiting'):
                bytes_available = self.client.socket.in_waiting
                if bytes_available > 0:
                    response = self.client.socket.read(bytes_available)
                    logger.debug(f"Respuesta 0x41: {response.hex()} ({len(response)} bytes)")
                    
                    # Parsear: [unit, 0x41, byte_count, slave_id, run_indicator, ascii..., crc_l, crc_h]
                    if len(response) >= 7:  # Mínimo: unit+func+bc+sid+run+1char+crc
                        if response[0] == unit_id and response[1] == 0x41:
                            byte_count = response[2]
                            data_end = 3 + byte_count
                            
                            if len(response) >= data_end + 2:
                                # Verificar CRC
                                frame_no_crc = response[:data_end]
                                rx_crc = response[data_end] | (response[data_end+1] << 8)
                                calc_crc_val = calc_crc16(frame_no_crc)
                                
                                if rx_crc == calc_crc_val:
                                    # Extraer ASCII info (skip slave_id y run_indicator)
                                    ascii_data = response[5:data_end].decode('ascii', errors='ignore').strip()
                                    
                                    logger.info(f"✅ Identify 0x41 activado en unit {unit_id}")
                                    logger.info(f"   Info: {ascii_data[:80]}")
                                    
                                    self.stats['rx_frames'] += 1
                                    return ascii_data
                                else:
                                    logger.error(f"CRC error en 0x41: esperado 0x{calc_crc_val:04X}, recibido 0x{rx_crc:04X}")
                            else:
                                logger.error(f"Respuesta 0x41 incompleta: {len(response)} bytes, esperados >={data_end+2}")
                        elif response[1] == 0xC1:  # Excepción (0x41 | 0x80)
                            exc_code = response[2] if len(response) > 2 else 0
                            logger.error(f"Excepción Modbus en 0x41: código {exc_code}")
                        else:
                            logger.error(f"Respuesta 0x41 inválida: unit={response[0]}, func=0x{response[1]:02X}")
                    else:
                        logger.error(f"Respuesta 0x41 muy corta: {len(response)} bytes")
                else:
                    logger.warning(f"Sin respuesta a 0x41 de unit {unit_id}")
            
            self.stats['errors'] += 1
            return None
            
        except Exception as e:
            logger.error(f"Error al enviar 0x41 a unit {unit_id}: {e}", exc_info=True)
            self.stats['errors'] += 1
            return None
    
    # ========================================================================
    # DIAGNÓSTICO Y ESTADO DEL DISPOSITIVO
    # ========================================================================
    
    def read_device_info(self, unit_id: int) -> Optional[dict]:
        """
        Lee información básica del dispositivo (BLOQUE 1: HR 0x0000-0x0009).
        
        Args:
            unit_id: ID del dispositivo esclavo
            
        Returns:
            Dict con vendor_id, product_id, hw_version, fw_version, unit_id_echo,
            capabilities, uptime_s, status, errors. None si falla.
        """
        regs = self.read_holding_registers(unit_id, 0x0000, 10)
        if not regs or len(regs) < 10:
            return None
        
        return {
            'vendor_id': regs[0],
            'product_id': regs[1],
            'hw_version': f"{regs[2] >> 8}.{regs[2] & 0xFF}",
            'fw_version': f"{regs[3] >> 8}.{regs[3] & 0xFF}",
            'unit_id_echo': regs[4],
            'capabilities': regs[5],
            'uptime_s': (regs[7] << 16) | regs[6],  # 32-bit: HI, LO
            'status': regs[8],
            'errors': regs[9]
        }
    
    def read_device_diagnostics(self, unit_id: int) -> Optional[dict]:
        """
        Lee estadísticas de diagnóstico Modbus (BLOQUE 4: HR 0x0020-0x0025).
        
        Args:
            unit_id: ID del dispositivo esclavo
            
        Returns:
            Dict con rx_ok, crc_errors, exceptions, tx_ok, uart_overruns, last_exception.
            None si falla.
        """
        regs = self.read_holding_registers(unit_id, 0x0020, 6)
        if not regs or len(regs) < 6:
            return None
        
        return {
            'rx_ok': regs[0],
            'crc_errors': regs[1],
            'exceptions': regs[2],
            'tx_ok': regs[3],
            'uart_overruns': regs[4],
            'last_exception': regs[5]
        }
    
    def read_quality_flags(self, unit_id: int) -> Optional[int]:
        """
        Lee flags de calidad de medidas (IR 0x000B).
        
        Args:
            unit_id: ID del dispositivo esclavo
            
        Returns:
            Flags de calidad (bitmask) o None si falla
        """
        regs = self.read_input_registers(unit_id, 0x000B, 1)
        if not regs or len(regs) < 1:
            return None
        return regs[0]
    
    def decode_capabilities(self, cap: int) -> dict:
        """Decodifica bitmask de capacidades"""
        return {
            'rs485': bool(cap & 0x01),
            'mpu6050': bool(cap & 0x02),
            'identify': bool(cap & 0x04),
            'wind': bool(cap & 0x08),
            'load': bool(cap & 0x10)  # Bit 4: Load (HX711)
        }
    
    def decode_status(self, status: int) -> dict:
        """Decodifica bitmask de estado"""
        return {
            'ok': bool(status & 0x01),
            'mpu_ready': bool(status & 0x02),
            'cfg_dirty': bool(status & 0x04)
        }
    
    def get_stats(self) -> dict:
        """Retorna estadísticas del Master"""
        return {
            'port': self.port,
            'baudrate': self.baudrate,
            'connected': self.is_connected(),
            **self.stats,
            'per_unit_timeouts': {str(k): v for k, v in self._timeouts_per_unit.items()}
        }
