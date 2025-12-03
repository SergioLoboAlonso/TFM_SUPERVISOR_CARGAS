#!/usr/bin/env python3
"""
Demo de la ventana History - Visualización de datos históricos
Muestra cómo consultar y visualizar datos de la BD SQLite
"""

import requests
import json
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8080"

def print_header(title):
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)

def demo_history_api():
    """Demuestra el uso de la API de historial"""
    
    print_header("📊 DEMO: VENTANA HISTORY - VISUALIZACIÓN DE DATOS HISTÓRICOS")
    
    # 1. Estadísticas de BD
    print("\n1️⃣  ESTADÍSTICAS DE LA BASE DE DATOS")
    print("-" * 80)
    response = requests.get(f"{BASE_URL}/api/history/stats")
    stats = response.json()
    
    print(f"   📁 Ruta BD: {stats['db_path']}")
    print(f"   💾 Tamaño: {stats['db_size_mb']} MB")
    print(f"   🖥️  Dispositivos: {stats['device_count']}")
    print(f"   🔧 Sensores: {stats['sensor_count']}")
    print(f"   📈 Medidas totales: {stats['measurement_count']:,}")
    print(f"   ⚠️  Alertas: {stats['alert_count']}")
    
    # 2. Lista de dispositivos
    print("\n2️⃣  DISPOSITIVOS REGISTRADOS EN BD")
    print("-" * 80)
    response = requests.get(f"{BASE_URL}/api/history/devices")
    devices = response.json()['devices']
    
    for device in devices:
        caps = json.loads(device['capabilities'])
        last_seen = datetime.fromisoformat(device['last_seen'].replace('Z', '+00:00'))
        time_ago = datetime.now(last_seen.tzinfo) - last_seen
        
        print(f"\n   📟 Unit {device['unit_id']:02}: {device['alias']}")
        print(f"      ├─ RIG ID: {device['rig_id']}")
        print(f"      ├─ Vendor: {device['vendor_code']}")
        print(f"      ├─ Capabilities: {', '.join(caps)}")
        print(f"      └─ Última telemetría: hace {int(time_ago.total_seconds())}s")
    
    # 3. Sensores de un dispositivo
    print("\n3️⃣  SENSORES DEL DISPOSITIVO UNIT 2")
    print("-" * 80)
    response = requests.get(f"{BASE_URL}/api/history/sensors/2")
    data = response.json()
    sensors = data['sensors']
    
    print(f"   Dispositivo: {data['device']['alias']}")
    print(f"   Total sensores: {len(sensors)}\n")
    
    for sensor in sensors:
        alarm_str = ""
        if sensor.get('alarm_lo') or sensor.get('alarm_hi'):
            lo = f"{sensor['alarm_lo']:.1f}" if sensor['alarm_lo'] else "-∞"
            hi = f"{sensor['alarm_hi']:.1f}" if sensor['alarm_hi'] else "+∞"
            alarm_str = f" | Umbrales: [{lo}, {hi}]"
        
        print(f"   • {sensor['sensor_id']:25} | {sensor['type']:15} | {sensor['unit']}{alarm_str}")
    
    # 4. Datos históricos de un sensor
    print("\n4️⃣  DATOS HISTÓRICOS: UNIT_2_TILT_X (última hora)")
    print("-" * 80)
    response = requests.get(f"{BASE_URL}/api/history/data/UNIT_2_TILT_X?hours=1")
    data = response.json()
    
    print(f"   Sensor: {data['sensor_id']}")
    print(f"   Unidad: {data['unit']}")
    print(f"   Muestras: {data['stats']['count']}")
    print(f"   Mínimo: {data['stats']['min']:.3f} {data['unit']}")
    print(f"   Máximo: {data['stats']['max']:.3f} {data['unit']}")
    print(f"   Promedio: {data['stats']['avg']:.3f} {data['unit']}")
    
    # Últimas 5 medidas
    print("\n   📋 Últimas 5 medidas:")
    for i, m in enumerate(data['measurements'][-5:], 1):
        ts = datetime.fromisoformat(m['timestamp'].replace('Z', '+00:00'))
        print(f"      {i}. {ts.strftime('%H:%M:%S')} → {m['value']:.3f} {m['unit']} ({m['quality']})")
    
    # 5. Demostrar rango personalizado
    print("\n5️⃣  DATOS CON RANGO PERSONALIZADO (últimos 30 minutos)")
    print("-" * 80)
    now = datetime.utcnow()
    start = now - timedelta(minutes=30)
    
    response = requests.get(
        f"{BASE_URL}/api/history/data/UNIT_2_TEMP",
        params={
            'start': start.isoformat() + 'Z',
            'end': now.isoformat() + 'Z'
        }
    )
    data = response.json()
    
    print(f"   Sensor: {data['sensor_id']}")
    print(f"   Período: {start.strftime('%H:%M')} - {now.strftime('%H:%M')}")
    print(f"   Muestras: {data['stats']['count']}")
    print(f"   Temperatura Min: {data['stats']['min']:.2f}°C")
    print(f"   Temperatura Max: {data['stats']['max']:.2f}°C")
    print(f"   Temperatura Avg: {data['stats']['avg']:.2f}°C")
    
    # 6. Uso de la interfaz web
    print("\n6️⃣  CÓMO USAR LA INTERFAZ WEB")
    print("-" * 80)
    print("""
   🌐 Abre el navegador en: http://localhost:8080/history
   
   📝 Características:
      1. Lista de dispositivos en la columna izquierda
      2. Haz clic en un dispositivo para ver sus sensores
      3. Selecciona un sensor para visualizar su historial
      4. Elige rango temporal: 1h, 6h, 24h, 7 días, 30 días
      5. O usa rango personalizado con fecha/hora exacta
      6. Visualiza gráfico interactivo con Chart.js
      7. Ve estadísticas (min, max, avg) en tiempo real
      8. Tabla con todos los datos tabulados
   
   💡 Ventajas:
      ✅ Ver datos históricos incluso si el dispositivo está apagado
      ✅ Análisis retrospectivo de tendencias
      ✅ Detección de patrones y anomalías
      ✅ Exportación de datos (tabla copiable)
      ✅ Compatible con ThingsBoard Edge para sincronización
    """)
    
    print_header("✅ DEMO COMPLETADA")
    print("\n💡 La ventana History permite supervisar datos históricos sin perder")
    print("   información cuando los dispositivos se apagan o no estás supervisando.\n")


if __name__ == "__main__":
    try:
        demo_history_api()
    except requests.exceptions.ConnectionError:
        print("\n❌ Error: No se puede conectar al servidor Edge.")
        print("   Asegúrate de que el servicio tfm-edge esté activo:")
        print("   sudo systemctl status tfm-edge.service\n")
    except Exception as e:
        print(f"\n❌ Error: {e}\n")
        import traceback
        traceback.print_exc()
