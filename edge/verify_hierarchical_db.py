#!/usr/bin/env python3
"""
Script de verificación de estructura jerárquica de BD.
Muestra la jerarquía DEVICES → SENSORS → MEASUREMENTS.
"""

import sys
import json
from datetime import datetime, timedelta
from pathlib import Path

# Agregar path para imports
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from database import Database


def print_hierarchical_view():
    """Muestra vista jerárquica completa de la BD."""
    
    db = Database('edge_measurements.db')
    
    print("\n" + "="*80)
    print("📊 VISTA JERÁRQUICA DE LA BASE DE DATOS - EDGE LAYER")
    print("="*80)
    
    # Estadísticas generales
    stats = db.get_db_stats()
    print(f"\n📁 Base de datos: {stats['db_path']}")
    print(f"💾 Tamaño: {stats['db_size_mb']} MB")
    print(f"\n📈 Contenido:")
    print(f"   • Dispositivos: {stats['device_count']}")
    print(f"   • Sensores:     {stats['sensor_count']}")
    print(f"   • Medidas:      {stats['measurement_count']:,}")
    print(f"   • Alertas:      {stats['alert_count']}")
    
    # Obtener dispositivos
    devices = db.get_all_devices()
    
    print("\n" + "="*80)
    print("🖥️  DISPOSITIVOS (MODBUS RTU)")
    print("="*80)
    
    for device in devices:
        unit_id = device['unit_id']
        alias = device['alias'] or f"Unit_{unit_id}"
        capabilities = json.loads(device['capabilities'])
        rig_id = device['rig_id']
        last_seen = device['last_seen']
        
        print(f"\n┌─ 📟 UNIT {unit_id:02}: {alias}")
        print(f"│  ├─ RIG ID: {rig_id}")
        print(f"│  ├─ Vendor: {device.get('vendor_code', 'N/A')}")
        print(f"│  ├─ Capabilities: {', '.join(capabilities)}")
        print(f"│  └─ Última telemetría: {last_seen}")
        
        # Obtener sensores del dispositivo
        sensors = db.get_sensors_by_device(unit_id)
        
        if sensors:
            print(f"│")
            print(f"│  🔧 SENSORES ({len(sensors)}):")
            for sensor in sensors:
                sensor_id = sensor['sensor_id']
                sensor_type = sensor['type']
                unit = sensor['unit']
                alarm_lo = sensor.get('alarm_lo')
                alarm_hi = sensor.get('alarm_hi')
                
                # Formatear umbrales
                alarm_str = ""
                if alarm_lo is not None or alarm_hi is not None:
                    lo = f"{alarm_lo:.1f}" if alarm_lo is not None else "−∞"
                    hi = f"{alarm_hi:.1f}" if alarm_hi is not None else "+∞"
                    alarm_str = f" | Umbrales: [{lo}, {hi}] {unit}"
                
                print(f"│  │")
                print(f"│  ├─ • {sensor_id}")
                print(f"│  │    Tipo: {sensor_type} | Unidad: {unit}{alarm_str}")
                
                # Obtener última medida de este sensor (últimos 5 min)
                since = datetime.now() - timedelta(minutes=5)
                measurements = db.get_measurements(sensor_id=sensor_id, since=since, limit=1)
                
                if measurements:
                    last_meas = measurements[0]
                    value = last_meas['value']
                    quality = last_meas['quality']
                    timestamp = last_meas['timestamp']
                    
                    # Formatear timestamp
                    ts_parts = timestamp.split('T')
                    ts_display = ts_parts[1][:8] if len(ts_parts) > 1 else timestamp[-12:]
                    
                    print(f"│  │    📈 Última medida: {value:.2f} {unit} ({quality}) @ {ts_display}")
        
        print("│")
        print("└" + "─"*78)
    
    print("\n" + "="*80)
    print("✅ Estructura jerárquica: DEVICES → SENSORS → MEASUREMENTS")
    print("✅ Compatible con ThingsBoard Edge para sincronización")
    print("="*80 + "\n")


if __name__ == "__main__":
    try:
        print_hierarchical_view()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
