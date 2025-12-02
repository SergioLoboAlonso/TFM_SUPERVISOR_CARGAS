#!/usr/bin/env python3
"""
Script de prueba para LoadSensor HX711
======================================

Lee continuamente:
- Peso actual (IR 0x000C)
- Máximo de las últimas 100 muestras (IR 0x001B)

Uso:
    python test_load_sensor.py [--port /dev/ttyUSB0] [--unit-id 8]
"""
import sys
import time
import argparse
from pymodbus.client import ModbusSerialClient


def to_int16(val: int) -> int:
    """Convierte uint16 a int16 (complemento a 2)"""
    return val if val < 32768 else val - 65536


def read_load_sensor(client, unit_id: int):
    """Lee peso actual y máximo de 100 muestras"""
    try:
        # Leer peso actual (IR 0x000C) y máximo (IR 0x001B)
        # Estrategia: leer 0x000C (1 reg) y luego 0x001B (1 reg)
        
        # Peso actual
        result = client.read_input_registers(0x000C, 1, slave=unit_id)
        if result.isError():
            return None, None
        
        peso_raw = result.registers[0]
        peso_kg = to_int16(peso_raw) / 100.0
        
        # Máximo de 100 muestras
        result_max = client.read_input_registers(0x001B, 1, slave=unit_id)
        if result_max.isError():
            return peso_kg, None
        
        max_raw = result_max.registers[0]
        max_kg = to_int16(max_raw) / 100.0
        
        return peso_kg, max_kg
        
    except Exception as e:
        print(f"❌ Error al leer: {e}")
        return None, None


def main():
    parser = argparse.ArgumentParser(description='Test LoadSensor HX711 via Modbus RTU')
    parser.add_argument('--port', default='/dev/ttyUSB0', help='Puerto serie (default: /dev/ttyUSB0)')
    parser.add_argument('--unit-id', type=int, default=8, help='Unit ID del dispositivo (default: 8)')
    parser.add_argument('--baudrate', type=int, default=115200, help='Velocidad (default: 115200)')
    parser.add_argument('--interval', type=float, default=1.0, help='Intervalo entre lecturas en segundos (default: 1.0)')
    args = parser.parse_args()
    
    print(f"🔌 Conectando a {args.port} @ {args.baudrate} baud...")
    print(f"📡 Unit ID: {args.unit_id}")
    print(f"⏱️  Intervalo: {args.interval}s")
    print("-" * 60)
    
    # Crear cliente Modbus RTU
    client = ModbusSerialClient(
        port=args.port,
        baudrate=args.baudrate,
        timeout=1.0,
        parity='N',
        stopbits=1,
        bytesize=8
    )
    
    if not client.connect():
        print(f"❌ No se pudo conectar a {args.port}")
        print("   Verifica:")
        print("   1. Que el puerto sea correcto (ls /dev/tty*)")
        print("   2. Permisos del puerto (sudo usermod -a -G dialout $USER)")
        print("   3. Que el Arduino esté conectado y flasheado")
        return 1
    
    print("✅ Conectado\n")
    print("Leyendo LoadSensor... (Ctrl+C para salir)")
    print("=" * 60)
    print(f"{'Tiempo':<12} {'Peso (kg)':<15} {'Máx-100 (kg)':<15}")
    print("-" * 60)
    
    try:
        count = 0
        while True:
            peso_kg, max_kg = read_load_sensor(client, args.unit_id)
            
            timestamp = time.strftime("%H:%M:%S")
            
            if peso_kg is not None:
                peso_str = f"{peso_kg:>8.2f} kg"
            else:
                peso_str = "  --  error"
            
            if max_kg is not None:
                max_str = f"{max_kg:>8.2f} kg"
            else:
                max_str = "  --  error"
            
            print(f"{timestamp:<12} {peso_str:<15} {max_str:<15}", flush=True)
            
            count += 1
            if count % 10 == 0:
                print("-" * 60)
            
            time.sleep(args.interval)
            
    except KeyboardInterrupt:
        print("\n\n⏹️  Detenido por usuario")
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")
        return 1
    finally:
        client.close()
        print("🔌 Desconectado")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
