#!/usr/bin/env python3
"""
Script de diagnóstico Modbus RTU
Prueba comunicación directa con dispositivos esclavos
"""
import sys
import time
from pymodbus.client import ModbusSerialClient

# Configuración
PORT = '/dev/tty.usbmodem5A300455411'  # Tu puerto RS-485
BAUDRATE = 115200
TIMEOUT = 1.0

def test_connection():
    """Test 1: Conectar al puerto serie"""
    print("=" * 60)
    print("TEST 1: Conexión al puerto serie")
    print("=" * 60)
    
    try:
        client = ModbusSerialClient(
            port=PORT,
            baudrate=BAUDRATE,
            timeout=TIMEOUT,
            parity='N',
            stopbits=1,
            bytesize=8
        )
        
        if client.connect():
            print(f"✅ Conectado a {PORT} @ {BAUDRATE} bps")
            return client
        else:
            print(f"❌ No se pudo conectar a {PORT}")
            return None
            
    except Exception as e:
        print(f"❌ Error al conectar: {e}")
        return None


def test_single_device(client, unit_id):
    """Test 2: Probar un dispositivo específico"""
    print(f"\n{'=' * 60}")
    print(f"TEST 2: Dispositivo UnitID={unit_id}")
    print("=" * 60)
    
    # Intentar leer registro de información básica (0x0000 - Vendor ID)
    print(f"\n📡 Leyendo HR 0x0000 (Vendor ID)...")
    try:
        result = client.read_holding_registers(
            address=0x0000,
            count=1,
            slave=unit_id
        )
        
        if result.isError():
            print(f"❌ Error Modbus: {result}")
            return False
        else:
            vendor_id = result.registers[0]
            print(f"✅ Respuesta recibida: Vendor ID = 0x{vendor_id:04X}")
            return True
            
    except Exception as e:
        print(f"❌ Excepción: {e}")
        return False


def test_broadcast_discovery(client):
    """Test 3: Intentar broadcast (no espera respuesta)"""
    print(f"\n{'=' * 60}")
    print("TEST 3: Broadcast Discovery (UnitID=0)")
    print("=" * 60)
    print("⚠️  Nota: Broadcast NO genera respuesta según Modbus RTU")
    
    try:
        # En Modbus RTU, broadcast es UnitID=0
        # NO debería generar respuesta
        result = client.read_holding_registers(
            address=0x0400,  # REG_DISCOVERY_CTRL
            count=1,
            slave=0
        )
        
        # Si llegamos aquí, algo raro pasó
        print(f"⚠️  Respuesta inesperada: {result}")
        
    except Exception as e:
        print(f"✅ Broadcast enviado (sin respuesta esperada): {e}")


def test_range_scan(client, min_id=1, max_id=10):
    """Test 4: Escanear rango de UnitIDs"""
    print(f"\n{'=' * 60}")
    print(f"TEST 4: Escaneo completo {min_id}..{max_id}")
    print("=" * 60)
    
    found_devices = []
    
    for unit_id in range(min_id, max_id + 1):
        print(f"\n🔍 Probando UnitID {unit_id}...", end=' ')
        sys.stdout.flush()
        
        try:
            result = client.read_holding_registers(
                address=0x0000,
                count=1,
                slave=unit_id
            )
            
            if not result.isError():
                vendor_id = result.registers[0]
                print(f"✅ ENCONTRADO! Vendor=0x{vendor_id:04X}")
                found_devices.append(unit_id)
            else:
                print(f"❌ Sin respuesta")
                
        except Exception as e:
            print(f"❌ Timeout/Error: {str(e)[:30]}")
        
        time.sleep(0.1)  # Pequeña pausa entre requests
    
    return found_devices


def test_read_full_identity(client, unit_id):
    """Test 5: Leer identidad completa de un dispositivo"""
    print(f"\n{'=' * 60}")
    print(f"TEST 5: Leer identidad completa UnitID={unit_id}")
    print("=" * 60)
    
    try:
        # Leer 10 registros de información (0x0000-0x0009)
        result = client.read_holding_registers(
            address=0x0000,
            count=10,
            slave=unit_id
        )
        
        if result.isError():
            print(f"❌ Error: {result}")
            return False
        
        regs = result.registers
        print(f"\n📋 Información del dispositivo:")
        print(f"  Vendor ID:        0x{regs[0]:04X}")
        print(f"  Product ID:       0x{regs[1]:04X}")
        print(f"  HW Version:       {regs[2] >> 8}.{regs[2] & 0xFF}")
        print(f"  FW Version:       {regs[3] >> 8}.{regs[3] & 0xFF}")
        print(f"  Serial Number:    0x{regs[4]:04X}{regs[5]:04X}")
        print(f"  Build Date:       0x{regs[6]:04X}")
        print(f"  Capabilities:     0x{regs[7]:04X}")
        print(f"  Status Flags:     0x{regs[8]:04X}")
        print(f"  Error Flags:      0x{regs[9]:04X}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_raw_bytes(client, unit_id):
    """Test 6: Monitorear bytes crudos (si es posible)"""
    print(f"\n{'=' * 60}")
    print(f"TEST 6: Análisis de trama cruda")
    print("=" * 60)
    
    print("\n📝 Trama esperada para leer HR 0x0000, count=1:")
    print("   [UnitID] [0x03] [AddrH] [AddrL] [CountH] [CountL] [CRC_L] [CRC_H]")
    print(f"   [{unit_id:02X}] [03] [00] [00] [00] [01] [CRC] [CRC]")
    
    # pymodbus no expone fácilmente los bytes crudos, pero podemos inferir
    print("\n⚠️  Para ver bytes crudos, usa un analizador serie o modo debug de pymodbus")


def main():
    print("\n" + "=" * 60)
    print("🔧 DIAGNÓSTICO MODBUS RTU - Maestro vs Esclavo")
    print("=" * 60)
    print(f"\nPuerto: {PORT}")
    print(f"Baudrate: {BAUDRATE}")
    print(f"Timeout: {TIMEOUT}s")
    
    # Test 1: Conexión
    client = test_connection()
    if not client:
        print("\n❌ No se pudo conectar al puerto. Verifica:")
        print("   1. Cable RS-485 conectado")
        print("   2. Puerto correcto (ls /dev/tty.*)")
        print("   3. Permisos (ls -l /dev/tty.usbmodem*)")
        return
    
    # Test 2: Dispositivo específico (intenta UnitID=1 por defecto)
    print("\n¿Qué UnitID tiene tu dispositivo? (default: 1): ", end='')
    try:
        user_input = input().strip()
        test_unit_id = int(user_input) if user_input else 1
    except:
        test_unit_id = 1
    
    found = test_single_device(client, test_unit_id)
    
    if found:
        print("\n✅ DISPOSITIVO ENCONTRADO!")
        test_read_full_identity(client, test_unit_id)
        test_raw_bytes(client, test_unit_id)
    else:
        print("\n❌ Dispositivo no responde. Probando escaneo completo...")
        
        # Test 4: Escaneo
        print("\n¿Rango de escaneo? (min,max, default: 1,10): ", end='')
        try:
            user_input = input().strip()
            if user_input:
                parts = user_input.split(',')
                min_id = int(parts[0])
                max_id = int(parts[1])
            else:
                min_id, max_id = 1, 10
        except:
            min_id, max_id = 1, 10
        
        found_devices = test_range_scan(client, min_id, max_id)
        
        if found_devices:
            print(f"\n✅ Dispositivos encontrados: {found_devices}")
            print(f"\nProbando identidad del primero ({found_devices[0]})...")
            test_read_full_identity(client, found_devices[0])
        else:
            print("\n❌ NO SE ENCONTRÓ NINGÚN DISPOSITIVO")
            print("\n🔍 Posibles causas:")
            print("   PROBLEMA DEL ESCLAVO (Firmware):")
            print("   - El firmware no está respondiendo a Modbus")
            print("   - UnitID configurado diferente al esperado")
            print("   - Baudrate diferente (firmware vs maestro)")
            print("   - Firmware no inicializó correctamente el bus RS-485")
            print("   - LED de actividad no parpadea al hacer discovery?")
            print("\n   PROBLEMA DEL MAESTRO (Edge Layer):")
            print("   - Puerto incorrecto (verifica con: ls /dev/tty.*)")
            print("   - Baudrate incorrecto")
            print("   - Timeout muy corto")
            print("\n   PROBLEMA DE CABLEADO:")
            print("   - RS-485 A/B invertidos")
            print("   - GND común no conectado")
            print("   - Terminación de bus (resistencia 120Ω)")
            print("   - Cable demasiado largo o con ruido")
    
    # Cleanup
    client.close()
    print("\n" + "=" * 60)
    print("Diagnóstico completado")
    print("=" * 60)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Diagnóstico interrumpido por usuario")
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")
        import traceback
        traceback.print_exc()
