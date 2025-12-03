"""
============================================================================
EJEMPLO DE USO - Database Module
============================================================================

Demuestra cómo usar el módulo database.py para:
    1. Inicializar la BD
    2. Registrar sensores
    3. Guardar telemetría
    4. Generar alertas
    5. Consultar datos históricos
    6. Sincronizar con ThingsBoard

Este script puede ejecutarse de forma independiente para probar la BD.

============================================================================
"""

import sys
from pathlib import Path

# Agregar src/ al path para importar módulos
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from database import Database
from datetime import datetime, timedelta
import random


def ejemplo_completo():
    """Ejemplo completo de uso del módulo Database"""
    
    # ========================================================================
    # 1. INICIALIZACIÓN
    # ========================================================================
    print("=" * 70)
    print("1. INICIALIZACIÓN DE BASE DE DATOS")
    print("=" * 70)
    
    # Usar BD de prueba en lugar de /opt/edge/db/measurements.db
    db_path = "/tmp/test_measurements.db"
    db = Database(db_path)
    
    stats = db.get_db_stats()
    print(f"✅ BD inicializada: {stats['db_path']}")
    print(f"   Tamaño: {stats['db_size_mb']} MB")
    print()
    
    # ========================================================================
    # 2. REGISTRAR SENSORES
    # ========================================================================
    print("=" * 70)
    print("2. REGISTRO DE SENSORES")
    print("=" * 70)
    
    # Sensor inclinómetro (MPU6050)
    db.upsert_sensor({
        'sensor_id': 'TILT_01',
        'type': 'tilt',
        'rig_id': 'RIG_01',
        'modbus_address': 1,
        'register': 0,  # IR_MED_ANGULO_X_CDEG
        'unit': 'deg',
        'alarm_lo': -5.0,   # Alarma si ángulo < -5°
        'alarm_hi': 5.0,    # Alarma si ángulo > 5°
        'enabled': 1
    })
    print("✅ Sensor TILT_01 registrado (inclinómetro, umbrales ±5°)")
    
    # Sensor anemómetro
    db.upsert_sensor({
        'sensor_id': 'WIND_01',
        'type': 'wind',
        'rig_id': 'RIG_01',
        'modbus_address': 2,
        'register': 13,  # IR_MED_VIENTO_VELOCIDAD
        'unit': 'm_s',
        'alarm_lo': None,
        'alarm_hi': 25.0,   # Alarma si viento > 25 m/s
        'enabled': 1
    })
    print("✅ Sensor WIND_01 registrado (anemómetro, umbral 25 m/s)")
    
    # Sensor de carga
    db.upsert_sensor({
        'sensor_id': 'LOAD_A1',
        'type': 'load',
        'rig_id': 'RIG_02',
        'modbus_address': 3,
        'register': 12,  # IR_MED_PESO_KG
        'unit': 'kg',
        'alarm_lo': 0.0,
        'alarm_hi': 500.0,  # Alarma si carga > 500 kg
        'enabled': 1
    })
    print("✅ Sensor LOAD_A1 registrado (celda de carga, umbral 500 kg)")
    print()
    
    # Listar sensores
    sensors = db.get_all_sensors()
    print(f"📊 Total de sensores activos: {len(sensors)}")
    for s in sensors:
        print(f"   - {s['sensor_id']}: {s['type']} en {s['rig_id']} "
              f"(Modbus addr={s['modbus_address']}, "
              f"umbrales={s['alarm_lo']}..{s['alarm_hi']})")
    print()
    
    # ========================================================================
    # 3. GUARDAR TELEMETRÍA
    # ========================================================================
    print("=" * 70)
    print("3. INSERCIÓN DE TELEMETRÍA")
    print("=" * 70)
    
    # Simular 10 lecturas de cada sensor en las últimas 2 horas
    now = datetime.utcnow()
    
    for i in range(10):
        timestamp = now - timedelta(minutes=12*i)  # Cada 12 minutos
        
        # Inclinómetro (ángulo variable)
        angle_x = random.uniform(-3.0, 6.5)  # Puede superar umbral
        quality = 'ALARM' if angle_x > 5.0 else 'OK'
        
        db.insert_measurement({
            'sensor_id': 'TILT_01',
            'type': 'tilt',
            'value': angle_x,
            'unit': 'deg',
            'quality': quality,
            'timestamp': timestamp
        })
        
        # Anemómetro (viento variable)
        wind_speed = random.uniform(8.0, 28.0)  # Puede superar umbral
        quality = 'ALARM' if wind_speed > 25.0 else 'OK'
        
        db.insert_measurement({
            'sensor_id': 'WIND_01',
            'type': 'wind',
            'value': wind_speed,
            'unit': 'm_s',
            'quality': quality,
            'timestamp': timestamp
        })
        
        # Sensor de carga (peso variable)
        load = random.uniform(100.0, 550.0)  # Puede superar umbral
        quality = 'ALARM' if load > 500.0 else 'OK'
        
        db.insert_measurement({
            'sensor_id': 'LOAD_A1',
            'type': 'load',
            'value': load,
            'unit': 'kg',
            'quality': quality,
            'timestamp': timestamp
        })
    
    print(f"✅ Insertadas 30 medidas (10 por sensor)")
    
    stats = db.get_db_stats()
    print(f"📊 Total de medidas en BD: {stats['measurement_count']}")
    print()
    
    # ========================================================================
    # 4. CONSULTAR TELEMETRÍA
    # ========================================================================
    print("=" * 70)
    print("4. CONSULTA DE TELEMETRÍA HISTÓRICA")
    print("=" * 70)
    
    # Últimas 5 medidas del inclinómetro
    tilt_data = db.get_measurements(sensor_id='TILT_01', limit=5)
    print(f"\n📈 Últimas 5 medidas de TILT_01:")
    for m in tilt_data:
        print(f"   {m['timestamp']}: {m['value']:.2f} {m['unit']} [{m['quality']}]")
    
    # Últimas 5 medidas del anemómetro
    wind_data = db.get_measurements(sensor_id='WIND_01', limit=5)
    print(f"\n📈 Últimas 5 medidas de WIND_01:")
    for m in wind_data:
        print(f"   {m['timestamp']}: {m['value']:.2f} {m['unit']} [{m['quality']}]")
    
    # Medidas de la última hora
    since = now - timedelta(hours=1)
    recent = db.get_measurements(since=since, limit=100)
    print(f"\n📈 Medidas de la última hora: {len(recent)} registros")
    print()
    
    # ========================================================================
    # 5. GENERAR ALERTAS
    # ========================================================================
    print("=" * 70)
    print("5. GENERACIÓN DE ALERTAS")
    print("=" * 70)
    
    # Simular motor de alertas: revisar últimas medidas y generar alertas
    tilt_latest = db.get_measurements(sensor_id='TILT_01', limit=1)[0]
    if tilt_latest['quality'] == 'ALARM':
        db.insert_alert({
            'level': 'ALARM',
            'code': 'TILT_LIMIT_EXCEEDED',
            'message': f"Inclinación de {tilt_latest['value']:.2f}° supera umbral de 5.0°",
            'sensor_id': 'TILT_01',
            'rig_id': 'RIG_01'
        })
        print("⚠️  Alerta generada: TILT_LIMIT_EXCEEDED")
    
    wind_latest = db.get_measurements(sensor_id='WIND_01', limit=1)[0]
    if wind_latest['quality'] == 'ALARM':
        db.insert_alert({
            'level': 'CRITICAL',
            'code': 'WIND_CRITICAL',
            'message': f"Viento de {wind_latest['value']:.1f} m/s supera umbral crítico de 25.0 m/s",
            'sensor_id': 'WIND_01',
            'rig_id': 'RIG_01'
        })
        print("🚨 Alerta generada: WIND_CRITICAL")
    
    load_latest = db.get_measurements(sensor_id='LOAD_A1', limit=1)[0]
    if load_latest['quality'] == 'ALARM':
        db.insert_alert({
            'level': 'WARN',
            'code': 'LOAD_HIGH',
            'message': f"Carga de {load_latest['value']:.1f} kg supera umbral de 500.0 kg",
            'sensor_id': 'LOAD_A1',
            'rig_id': 'RIG_02'
        })
        print("⚠️  Alerta generada: LOAD_HIGH")
    
    print()
    
    # Consultar alertas no reconocidas
    alerts = db.get_alerts(ack=False, limit=10)
    print(f"📋 Alertas activas (no reconocidas): {len(alerts)}")
    for a in alerts:
        icon = "🚨" if a['level'] == 'CRITICAL' else "⚠️"
        print(f"   {icon} [{a['level']}] {a['code']}: {a['message']}")
    print()
    
    # ========================================================================
    # 6. SINCRONIZACIÓN CON THINGSBOARD
    # ========================================================================
    print("=" * 70)
    print("6. SIMULACIÓN DE BRIDGE THINGSBOARD")
    print("=" * 70)
    
    # Obtener medidas pendientes de enviar
    unsent = db.get_unsent_measurements(limit=100)
    print(f"📤 Medidas pendientes de enviar a ThingsBoard: {len(unsent)}")
    
    if unsent:
        # Simular publicación a ThingsBoard
        # En producción: aquí iría la lógica de HTTP POST o MQTT publish
        print("   Publicando medidas a ThingsBoard...")
        
        # Agrupar por sensor para publicar telemetría agregada
        by_sensor = {}
        for m in unsent:
            sensor_id = m['sensor_id']
            if sensor_id not in by_sensor:
                by_sensor[sensor_id] = []
            by_sensor[sensor_id].append(m)
        
        for sensor_id, measurements in by_sensor.items():
            # Calcular agregados (último valor, min, max, avg)
            values = [m['value'] for m in measurements]
            telemetry_payload = {
                'last_value': values[0],
                'min_value': min(values),
                'max_value': max(values),
                'avg_value': sum(values) / len(values),
                'sample_count': len(values)
            }
            print(f"   - {sensor_id}: {telemetry_payload}")
        
        # Marcar como enviadas
        measurement_ids = [m['id'] for m in unsent]
        db.mark_as_sent(measurement_ids)
        print(f"✅ {len(measurement_ids)} medidas marcadas como enviadas")
    
    print()
    
    # Verificar que no quedan pendientes
    unsent_after = db.get_unsent_measurements()
    print(f"📊 Medidas pendientes tras sincronización: {len(unsent_after)}")
    print()
    
    # ========================================================================
    # 7. ESTADÍSTICAS FINALES
    # ========================================================================
    print("=" * 70)
    print("7. ESTADÍSTICAS FINALES")
    print("=" * 70)
    
    final_stats = db.get_db_stats()
    print(f"📊 Estadísticas de BD:")
    print(f"   Ruta: {final_stats['db_path']}")
    print(f"   Tamaño: {final_stats['db_size_mb']} MB")
    print(f"   Sensores: {final_stats['sensor_count']}")
    print(f"   Medidas: {final_stats['measurement_count']}")
    print(f"   Alertas: {final_stats['alert_count']}")
    print()
    
    # ========================================================================
    # 8. LIMPIEZA (OPCIONAL)
    # ========================================================================
    print("=" * 70)
    print("8. LIMPIEZA DE DATOS ANTIGUOS (OPCIONAL)")
    print("=" * 70)
    
    # En producción, esto se ejecutaría periódicamente
    # Aquí lo comentamos para no borrar los datos de ejemplo
    # deleted = db.cleanup_old_data(days=30)
    # print(f"🗑️  Eliminadas {deleted} medidas antiguas (>30 días)")
    
    print("⏭️  Omitido (para preservar datos de ejemplo)")
    print()
    
    print("=" * 70)
    print("✅ EJEMPLO COMPLETADO")
    print("=" * 70)
    print(f"Base de datos de prueba: {db_path}")
    print("Para inspeccionarla:")
    print(f"  sqlite3 {db_path}")
    print(f"  sqlite> .tables")
    print(f"  sqlite> SELECT * FROM sensors;")
    print()


if __name__ == '__main__':
    ejemplo_completo()
