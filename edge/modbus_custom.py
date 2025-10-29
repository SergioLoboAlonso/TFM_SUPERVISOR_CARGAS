"""
modbus_custom.py — Funciones Modbus custom 0x11 y 0x41 para pymodbus

Implementa las funciones propietarias del firmware:
- 0x11: Report Slave ID (Modbus estándar, pero pymodbus tiene soporte nativo)
- 0x41: Identify Blink + Info (función propietaria que dispara LED + devuelve info)
"""

from pymodbus.pdu import ModbusRequest, ModbusResponse
from pymodbus.exceptions import ModbusException
import struct


class IdentifyBlinkRequest(ModbusRequest):
    """
    Función 0x41 propietaria: Identify Blink + Info
    
    Request: [slave][0x41][crc_lo][crc_hi]
    Response: [slave][0x41][byteCount][slaveId][runIndicator][ascii...][crc_lo][crc_hi]
    
    Similar a 0x11 pero dispara automáticamente el LED de identificación.
    """
    function_code = 0x41
    
    def __init__(self, slave=1, **kwargs):
        ModbusRequest.__init__(self, **kwargs)
        self.slave_id = slave
    
    def encode(self):
        """Sin payload, solo el function code"""
        return b''
    
    def decode(self, data):
        """Request no tiene datos adicionales"""
        pass


class IdentifyBlinkResponse(ModbusResponse):
    """
    Respuesta de función 0x41
    
    Formato: [byteCount][slaveId][runIndicator(0xFF=running)][ascii_info...]
    """
    function_code = 0x41
    _rtu_byte_count_pos = 2  # Posición del byte count en frame RTU
    
    def __init__(self, **kwargs):
        ModbusResponse.__init__(self, **kwargs)
        self.byte_count = 0
        self.slave_id = 0
        self.status = False  # Running indicator
        self.identifier = b''
    
    def encode(self):
        """Codificar respuesta (no usado en cliente)"""
        result = struct.pack('B', self.byte_count)
        result += struct.pack('B', self.slave_id)
        result += struct.pack('B', 0xFF if self.status else 0x00)
        result += self.identifier
        return result
    
    def decode(self, data):
        """
        Decodificar respuesta del servidor
        data: [byteCount][slaveId][runIndicator][ascii...]
        """
        if len(data) < 3:
            raise ModbusException(f"Invalid response length: {len(data)}")
        
        self.byte_count = int(data[0])
        self.slave_id = int(data[1])
        self.status = (data[2] == 0xFF)
        
        # ASCII info: byteCount incluye slaveId(1) + runIndicator(1) + ascii
        ascii_len = self.byte_count - 2
        if len(data) >= 3 + ascii_len:
            self.identifier = data[3:3+ascii_len]
        else:
            self.identifier = data[3:]
    
    @classmethod
    def calculateRtuFrameSize(cls, buffer):
        """
        Calcular tamaño del frame RTU completo
        buffer: bytes recibidos hasta ahora
        
        Frame RTU: [slave][func][byteCount][data...][crc_lo][crc_hi]
        Mínimo: 1 + 1 + 1 + 2 (slaveId + running) + 2 (CRC) = 7 bytes
        """
        if len(buffer) < 3:
            return 0  # Necesitamos al menos [slave][func][byteCount]
        
        byte_count = buffer[2]  # byteCount en posición 2
        # Frame total: slave(1) + func(1) + byteCount(1) + data(byteCount) + CRC(2)
        return 1 + 1 + 1 + byte_count + 2


def register_custom_functions(client):
    """
    Registrar funciones custom en el decoder de pymodbus
    
    Args:
        client: ModbusSerialClient instance
    """
    client.framer.decoder.register(IdentifyBlinkResponse)


def report_slave_id(client, slave=1):
    """
    Ejecutar función 0x11 Report Slave ID (usa implementación nativa de pymodbus)
    
    Args:
        client: ModbusSerialClient
        slave: Unit ID del dispositivo
    
    Returns:
        dict: {"slave_id": int, "running": bool, "info": str}
    """
    resp = client.report_slave_id(slave=slave)
    
    if resp.isError():
        raise ModbusException(f"report_slave_id error: {resp}")
    
    # Parse response
    # identifier format: [slaveId][runIndicator][ascii...]
    if len(resp.identifier) < 2:
        raise ModbusException("Invalid identifier length")
    
    slave_id = resp.identifier[0]
    running = (resp.identifier[1] == 0xFF)
    info_bytes = resp.identifier[2:]
    info_text = info_bytes.decode('ascii', errors='ignore')
    
    return {
        "slave_id": slave_id,
        "running": running,
        "info": info_text
    }


def identify_blink(client, slave=1):
    """
    Ejecutar función 0x41 Identify Blink + Info
    
    Dispara LED de identificación y devuelve info del dispositivo.
    
    Args:
        client: ModbusSerialClient
        slave: Unit ID del dispositivo
    
    Returns:
        dict: {"slave_id": int, "running": bool, "info": str}
    """
    req = IdentifyBlinkRequest(slave=slave)
    resp = client.execute(req)
    
    if resp.isError():
        raise ModbusException(f"identify_blink error: {resp}")
    
    info_text = resp.identifier.decode('ascii', errors='ignore')
    
    return {
        "slave_id": resp.slave_id,
        "running": resp.status,
        "info": info_text
    }


if __name__ == "__main__":
    """Test de funciones custom"""
    from pymodbus.client import ModbusSerialClient
    import time
    
    PORT = "/dev/tty.usbmodem5A300455411"
    BAUD = 115200
    SLAVE = 2
    
    cli = ModbusSerialClient(port=PORT, baudrate=BAUD, parity='N', stopbits=1, bytesize=8, timeout=2)
    
    if not cli.connect():
        print("✗ No pudo conectar")
        exit(1)
    
    print("✓ Conectado")
    time.sleep(0.2)
    
    # Registrar funciones custom
    register_custom_functions(cli)
    
    # Test 0x11
    print("\n--- Test 0x11 Report Slave ID ---")
    try:
        result = report_slave_id(cli, slave=SLAVE)
        print(f"Slave ID: {result['slave_id']}")
        print(f"Running: {result['running']}")
        print(f"Info: {result['info']}")
    except Exception as e:
        print(f"Error: {e}")
    
    time.sleep(0.5)
    
    # Test 0x41
    print("\n--- Test 0x41 Identify Blink ---")
    try:
        result = identify_blink(cli, slave=SLAVE)
        print(f"Slave ID: {result['slave_id']}")
        print(f"Running: {result['running']}")
        print(f"Info: {result['info']}")
        print("✓ LED debería estar parpadeando")
    except Exception as e:
        print(f"Error: {e}")
    
    cli.close()
    print("\n✓ Test completado")
