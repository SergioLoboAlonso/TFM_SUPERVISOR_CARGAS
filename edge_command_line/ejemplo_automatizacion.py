#!/usr/bin/env python3
"""
Script de ejemplo: Discovery y monitoreo automático

Demuestra cómo usar edge_cli.py en scripts automatizados.
"""
import subprocess
import sys
import time

def run_command(cmd):
    """Ejecuta comando y muestra salida"""
    print(f"\n{'='*70}")
    print(f"Ejecutando: {' '.join(cmd)}")
    print('='*70)
    
    result = subprocess.run(cmd, capture_output=False)
    return result.returncode == 0

def main():
    """Script de automatización de ejemplo"""
    
    # 1. Discovery
    print("\n🔍 PASO 1: Discovery de dispositivos...")
    if not run_command(['python3', 'edge_cli.py', '--discover']):
        print("❌ Error en discovery")
        return 1
    
    time.sleep(2)
    
    # 2. Listar dispositivos encontrados
    print("\n📋 PASO 2: Listando dispositivos...")
    if not run_command(['python3', 'edge_cli.py', '--list']):
        print("❌ Error listando dispositivos")
        return 1
    
    time.sleep(2)
    
    # 3. Lectura de telemetría (ejemplo con UnitID 16)
    print("\n📊 PASO 3: Lectura de telemetría (ejemplo UnitID 16)...")
    print("ℹ️  Si no hay dispositivo en UnitID 16, cambia el número en el script")
    
    # Nota: Esto fallará si no hay dispositivo en UnitID 16
    # Modificar según dispositivos encontrados en paso 1
    run_command(['python3', 'edge_cli.py', '--poll', '16', '--interval', '2'])
    
    print("\n✅ Script de ejemplo completado")
    return 0

if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Script interrumpido por usuario")
        sys.exit(1)
