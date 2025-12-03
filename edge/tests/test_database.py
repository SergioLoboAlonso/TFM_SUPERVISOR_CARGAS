"""
============================================================================
TEST DATABASE MODULE
============================================================================

Tests unitarios básicos para verificar el módulo database.py

Ejecutar:
    pytest test_database.py -v
    
O sin pytest:
    python3 test_database.py

============================================================================
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta

# Agregar src/ al path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from database import Database, init_db


def test_init_db():
    """Test: Inicialización de BD crea archivo y tablas"""
    print("\n🧪 Test: Inicialización de BD")
    
    db_path = "/tmp/test_init.db"
    
    # Limpiar si existe
    if os.path.exists(db_path):
        os.remove(db_path)
    
    # Inicializar
    init_db(db_path)
    
    # Verificar que se creó el archivo
    assert os.path.exists(db_path), "Archivo de BD no creado"
    
    # Verificar tamaño > 0
    assert os.path.getsize(db_path) > 0, "BD vacía (0 bytes)"
    
    print("   ✅ BD creada correctamente")
    os.remove(db_path)


def test_sensor_operations():
    """Test: CRUD de sensores"""
    print("\n🧪 Test: Operaciones con sensores")
    
    db_path = "/tmp/test_sensors.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    
    db = Database(db_path)
    
    # INSERT
    db.upsert_sensor({
        'sensor_id': 'TEST_TILT_01',
        'type': 'tilt',
        'rig_id': 'TEST_RIG',
        'modbus_address': 99,
        'register': 0,
        'unit': 'deg',
        'alarm_lo': -10.0,
        'alarm_hi': 10.0,
        'enabled': 1
    })
    print("   ✅ Sensor insertado")
    
    # READ
    sensor = db.get_sensor('TEST_TILT_01')
    assert sensor is not None, "Sensor no encontrado"
    assert sensor['type'] == 'tilt', f"Tipo incorrecto: {sensor['type']}"
    assert sensor['modbus_address'] == 99, f"Modbus addr incorrecto: {sensor['modbus_address']}"
    print("   ✅ Sensor leído correctamente")
    
    # UPDATE
    db.upsert_sensor({
        'sensor_id': 'TEST_TILT_01',
        'type': 'tilt',
        'rig_id': 'TEST_RIG',
        'modbus_address': 99,
        'register': 0,
        'unit': 'deg',
        'alarm_lo': -5.0,  # Cambiado
        'alarm_hi': 5.0,   # Cambiado
        'enabled': 1
    })
    sensor_updated = db.get_sensor('TEST_TILT_01')
    assert sensor_updated['alarm_hi'] == 5.0, "UPDATE no funcionó"
    print("   ✅ Sensor actualizado")
    
    # LIST
    all_sensors = db.get_all_sensors()
    assert len(all_sensors) == 1, f"Esperado 1 sensor, encontrados {len(all_sensors)}"
    print("   ✅ Listado de sensores correcto")
    
    os.remove(db_path)


def test_measurement_operations():
    """Test: CRUD de medidas"""
    print("\n🧪 Test: Operaciones con medidas")
    
    db_path = "/tmp/test_measurements.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    
    db = Database(db_path)
    
    # Crear sensor primero
    db.upsert_sensor({
        'sensor_id': 'TEST_WIND',
        'type': 'wind',
        'rig_id': 'RIG_01',
        'modbus_address': 1,
        'register': 13,
        'unit': 'm_s',
        'alarm_hi': 25.0,
        'enabled': 1
    })
    
    # INSERT medidas
    now = datetime.utcnow()
    for i in range(5):
        timestamp = now - timedelta(minutes=i)
        db.insert_measurement({
            'sensor_id': 'TEST_WIND',
            'type': 'wind',
            'value': 10.0 + i,
            'unit': 'm_s',
            'quality': 'OK',
            'timestamp': timestamp
        })
    print("   ✅ 5 medidas insertadas")
    
    # READ últimas medidas
    latest = db.get_measurements(sensor_id='TEST_WIND', limit=3)
    assert len(latest) == 3, f"Esperadas 3 medidas, obtenidas {len(latest)}"
    assert latest[0]['value'] == 10.0, "Primera medida incorrecta (orden DESC)"
    print("   ✅ Consulta de últimas medidas OK")
    
    # READ con filtro de tiempo (últimas 2 horas = todas las 5 medidas)
    since = now - timedelta(hours=2)
    recent = db.get_measurements(sensor_id='TEST_WIND', since=since, limit=10)
    assert len(recent) == 5, f"Esperadas 5 medidas recientes, obtenidas {len(recent)}"
    print("   ✅ Filtro por timestamp OK")
    
    # Verificar sent_to_cloud
    unsent = db.get_unsent_measurements()
    assert len(unsent) == 5, f"Esperadas 5 no enviadas, obtenidas {len(unsent)}"
    print("   ✅ Filtro sent_to_cloud OK")
    
    # Marcar como enviadas
    ids = [m['id'] for m in unsent[:3]]
    db.mark_as_sent(ids)
    unsent_after = db.get_unsent_measurements()
    assert len(unsent_after) == 2, f"Esperadas 2 pendientes, quedan {len(unsent_after)}"
    print("   ✅ mark_as_sent() OK")
    
    os.remove(db_path)


def test_alert_operations():
    """Test: CRUD de alertas"""
    print("\n🧪 Test: Operaciones con alertas")
    
    db_path = "/tmp/test_alerts.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    
    db = Database(db_path)
    
    # INSERT alertas
    alert_id_1 = db.insert_alert({
        'level': 'WARN',
        'code': 'TEST_WARNING',
        'message': 'Test warning message',
        'sensor_id': None,
        'rig_id': 'RIG_01'
    })
    
    alert_id_2 = db.insert_alert({
        'level': 'CRITICAL',
        'code': 'TEST_CRITICAL',
        'message': 'Test critical alert',
        'sensor_id': 'SENSOR_01',
        'rig_id': 'RIG_01'
    })
    
    print("   ✅ 2 alertas insertadas")
    
    # READ alertas no reconocidas
    unack = db.get_alerts(ack=False)
    assert len(unack) == 2, f"Esperadas 2 no reconocidas, obtenidas {len(unack)}"
    print("   ✅ Filtro ack=False OK")
    
    # Filtrar por nivel
    critical = db.get_alerts(level='CRITICAL')
    assert len(critical) == 1, f"Esperada 1 CRITICAL, obtenidas {len(critical)}"
    assert critical[0]['code'] == 'TEST_CRITICAL', "Filtro por nivel incorrecto"
    print("   ✅ Filtro por nivel OK")
    
    # Reconocer alerta
    db.acknowledge_alert(alert_id_1)
    unack_after = db.get_alerts(ack=False)
    assert len(unack_after) == 1, "acknowledge_alert() no funcionó"
    print("   ✅ acknowledge_alert() OK")
    
    os.remove(db_path)


def test_db_stats_and_cleanup():
    """Test: Estadísticas y limpieza"""
    print("\n🧪 Test: Estadísticas y limpieza")
    
    db_path = "/tmp/test_stats.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    
    db = Database(db_path)
    
    # Crear sensor
    db.upsert_sensor({
        'sensor_id': 'STAT_SENSOR',
        'type': 'tilt',
        'rig_id': 'RIG',
        'modbus_address': 1,
        'register': 0,
        'unit': 'deg',
        'enabled': 1
    })
    
    # Insertar medidas (algunas antiguas)
    now = datetime.utcnow()
    
    # 5 medidas recientes
    for i in range(5):
        db.insert_measurement({
            'sensor_id': 'STAT_SENSOR',
            'type': 'tilt',
            'value': i,
            'unit': 'deg',
            'timestamp': now - timedelta(hours=i)
        })
    
    # 3 medidas antiguas (>31 días)
    for i in range(3):
        db.insert_measurement({
            'sensor_id': 'STAT_SENSOR',
            'type': 'tilt',
            'value': 100 + i,
            'unit': 'deg',
            'timestamp': now - timedelta(days=32 + i)
        })
    
    # Estadísticas
    stats = db.get_db_stats()
    assert stats['sensor_count'] == 1, "Stats: sensor_count incorrecto"
    assert stats['measurement_count'] == 8, "Stats: measurement_count incorrecto"
    assert stats['db_size_mb'] > 0, "Stats: db_size_mb debe ser > 0"
    print(f"   ✅ Estadísticas OK: {stats['measurement_count']} medidas, {stats['db_size_mb']} MB")
    
    # Limpieza (>30 días)
    deleted = db.cleanup_old_data(days=30)
    assert deleted == 3, f"Esperadas 3 medidas eliminadas, eliminadas {deleted}"
    
    stats_after = db.get_db_stats()
    assert stats_after['measurement_count'] == 5, "Limpieza incorrecta"
    print(f"   ✅ Limpieza OK: {deleted} medidas antiguas eliminadas")
    
    os.remove(db_path)


def test_foreign_key_constraint():
    """Test: Foreign keys (sensor_id en measurements)"""
    print("\n🧪 Test: Foreign key constraints")
    
    db_path = "/tmp/test_fk.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    
    db = Database(db_path)
    
    # Intentar insertar medida sin sensor existente
    # NOTA: SQLite NO fuerza foreign keys por defecto, este test es informativo
    try:
        db.insert_measurement({
            'sensor_id': 'NONEXISTENT_SENSOR',
            'type': 'tilt',
            'value': 1.0,
            'unit': 'deg'
        })
        # Si llegamos aquí, FK no están habilitadas (comportamiento por defecto)
        print("   ⚠️  Foreign keys NO habilitadas (comportamiento estándar SQLite)")
    except Exception as e:
        print(f"   ✅ Foreign key violation detectada: {e}")
    
    os.remove(db_path)


def run_all_tests():
    """Ejecuta todos los tests"""
    print("=" * 70)
    print("🧪 TEST SUITE - Database Module")
    print("=" * 70)
    
    tests = [
        test_init_db,
        test_sensor_operations,
        test_measurement_operations,
        test_alert_operations,
        test_db_stats_and_cleanup,
        test_foreign_key_constraint
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"   ❌ FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            failed += 1
    
    print("\n" + "=" * 70)
    print(f"📊 RESULTADOS: {passed} passed, {failed} failed")
    print("=" * 70)
    
    if failed == 0:
        print("✅ TODOS LOS TESTS PASARON")
        return 0
    else:
        print("❌ ALGUNOS TESTS FALLARON")
        return 1


if __name__ == '__main__':
    exit_code = run_all_tests()
    sys.exit(exit_code)
