#!/usr/bin/env python3
"""Test directo de capabilities del dispositivo UnitID 2"""

from pymodbus.client import ModbusSerialClient

PORT = "/dev/cu.usbmodem5A300455411"
BAUDRATE = 115200
UNIT_ID = 2

# Registros de información
HR_INFO_VENDOR_ID = 0x0000
HR_INFO_PRODUCTO_ID = 0x0001
HR_INFO_VERSION_HW = 0x0002
HR_INFO_VERSION_FW = 0x0003
HR_INFO_ID_UNIDAD = 0x0004
HR_INFO_CAPACIDADES = 0x0005

# Capabilities bits
DEV_CAP_RS485 = (1<<0)
DEV_CAP_MPU6050 = (1<<1)
DEV_CAP_IDENT = (1<<2)
DEV_CAP_WIND = (1<<3)
DEV_CAP_LOAD = (1<<4)

def main():
    client = ModbusSerialClient(
        port=PORT,
        baudrate=BAUDRATE,
        bytesize=8,
        parity='N',
        stopbits=1,
        timeout=1.0
    )
    
    if not client.connect():
        print(f"❌ No se pudo conectar a {PORT}")
        return
    
    print(f"✅ Conectado a {PORT} @ {BAUDRATE} baud")
    print(f"📡 Leyendo registros de UnitID {UNIT_ID}...\n")
    
    # Leer bloque de información (0x0000-0x0005 = 6 registros)
    result = client.read_holding_registers(HR_INFO_VENDOR_ID, 6, slave=UNIT_ID)
    
    if result.isError():
        print(f"❌ Error al leer registros: {result}")
        client.close()
        return
    
    regs = result.registers
    vendor_id = regs[0]
    product_id = regs[1]
    hw_version = regs[2]
    fw_version = regs[3]
    unit_id = regs[4]
    capabilities = regs[5]
    
    print(f"Vendor ID:      0x{vendor_id:04X}  ({chr(vendor_id>>8)}{chr(vendor_id&0xFF)})")
    print(f"Product ID:     0x{product_id:04X}  ({chr(product_id>>8)}{chr(product_id&0xFF)})")
    print(f"HW Version:     0x{hw_version:04X}  ({(hw_version>>8)}.{(hw_version&0xFF)})")
    print(f"FW Version:     0x{fw_version:04X}  ({(fw_version>>8)}.{(fw_version&0xFF)})")
    print(f"Unit ID:        {unit_id}")
    print(f"Capabilities:   0x{capabilities:04X}  (bin: {capabilities:016b})")
    print()
    
    # Decodificar capabilities
    print("Capabilities detectadas:")
    if capabilities & DEV_CAP_RS485:
        print("  ✅ RS485 (bit 0)")
    if capabilities & DEV_CAP_MPU6050:
        print("  ✅ MPU6050 (bit 1)")
    if capabilities & DEV_CAP_IDENT:
        print("  ✅ IDENT (bit 2)")
    if capabilities & DEV_CAP_WIND:
        print("  ✅ WIND (bit 3)")
    if capabilities & DEV_CAP_LOAD:
        print("  ✅ LOAD (bit 4)")
    else:
        print("  ❌ LOAD NO DETECTADO (bit 4)")
    
    client.close()
    print("\n✅ Test completado")

if __name__ == "__main__":
    main()
