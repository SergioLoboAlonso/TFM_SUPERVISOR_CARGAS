#!/usr/bin/env python3
"""Test directo de lectura de peso del LoadSensor"""

from pymodbus.client import ModbusSerialClient

PORT = "/dev/cu.usbmodem5A300455411"
BAUDRATE = 115200
UNIT_ID = 2

# Registros de medición de peso
IR_MED_PESO_KG = 0x0009  # 30010 R  Peso en kg*100 (int16)

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
    print(f"📡 Leyendo peso de UnitID {UNIT_ID}...\n")
    
    for i in range(10):
        result = client.read_input_registers(IR_MED_PESO_KG, 1, slave=UNIT_ID)
        
        if result.isError():
            print(f"❌ Error al leer peso: {result}")
            continue
        
        # El registro es int16 en kg*100
        raw_value = result.registers[0]
        # Interpretar como signed int16
        if raw_value > 32767:
            signed_value = raw_value - 65536
        else:
            signed_value = raw_value
        
        weight_kg = signed_value / 100.0
        
        print(f"Lectura {i+1}: raw=0x{raw_value:04X} ({signed_value}) → {weight_kg:.2f} kg ({weight_kg*1000:.0f} g)")
        
        import time
        time.sleep(0.5)
    
    client.close()
    print("\n✅ Test completado")

if __name__ == "__main__":
    main()
