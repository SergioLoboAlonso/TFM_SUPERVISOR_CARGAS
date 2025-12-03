"""
============================================================================
DATABASE MODULE - Persistencia SQLite para Edge Layer
============================================================================

Arquitectura IIoT:
    Raspberry Pi (Edge) ──[Modbus RTU]──> Sensores (inclinómetros, carga, viento)
                    │
                    ├─> SQLite (measurements.db)
                    │     ├─ sensors: Config de sensores
                    │     ├─ measurements: Telemetría histórica
                    │     └─ alerts: Alertas locales
                    │
                    ├─> Motor de Alertas (lee de BD)
                    │
                    └─> Bridge ThingsBoard (lee de BD, publica agregados)

Responsabilidades:
    1. Crear y mantener el esquema de BD SQLite
    2. Proveer API de acceso a datos para:
       - PollingService → guardar telemetría
       - Motor de alertas → consultar umbrales y generar alertas
       - Bridge ThingsBoard → leer datos agregados y sincronizar
    3. Gestionar índices para rendimiento
    4. Limpieza automática de datos antiguos

Tablas:
    - sensors: Configuración de sensores físicos (tipo, umbrales, unit_id Modbus)
    - measurements: Series temporales de telemetría (value + quality + sent_to_cloud)
    - alerts: Alertas generadas localmente (nivel, código, ack)

============================================================================
"""

import sqlite3
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from contextlib import contextmanager
from logger import logger


# ============================================================================
# CONFIGURACIÓN
# ============================================================================

# Ruta de la base de datos (relativa al directorio edge/)
DB_PATH = "edge_measurements.db"  # Se creará en edge/edge_measurements.db

# Retención de datos (días)
DEFAULT_RETENTION_DAYS = 30


# ============================================================================
# INICIALIZACIÓN DE BASE DE DATOS
# ============================================================================

def init_db(db_path: str = DB_PATH) -> None:
    """
    Inicializa la base de datos SQLite con el esquema necesario para el Edge Layer.
    
    Esta función es idempotente: puede ejecutarse múltiples veces sin borrar datos.
    - Crea la carpeta de la BD si no existe
    - Crea las tablas si no existen (sensors, measurements, alerts)
    - Crea índices para optimizar consultas
    
    Tablas creadas:
        1. sensors: Configuración de sensores físicos
           - Identifica cada sensor por sensor_id lógico
           - Almacena tipo (tilt, wind, load), ubicación (rig_id)
           - Config Modbus (modbus_address, register)
           - Umbrales de alarma (alarm_lo, alarm_hi)
           
        2. measurements: Telemetría histórica
           - Series temporales de medidas (timestamp, value, unit)
           - Calidad de lectura (quality: OK, WARN, ALARM, ERROR_COMMS)
           - Flag de sincronización con cloud (sent_to_cloud)
           
        3. alerts: Alertas locales generadas en el Edge
           - Nivel de alerta (INFO, WARN, ALARM, CRITICAL)
           - Código y mensaje descriptivo
           - Estado de reconocimiento (ack)
    
    Args:
        db_path: Ruta completa al archivo SQLite (default: /opt/edge/db/measurements.db)
    
    Raises:
        sqlite3.Error: Si hay error al crear la BD
        OSError: Si no se puede crear el directorio
    """
    
    # 1. Crear directorio si no existe
    db_dir = Path(db_path).parent
    db_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"📁 Directorio de BD verificado: {db_dir}")
    
    # 2. Conectar a SQLite (crea el archivo si no existe)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # Acceso por nombre de columna
    cursor = conn.cursor()
    logger.info(f"🔌 Conexión abierta a BD: {db_path}")
    
    try:
        # ====================================================================
        # TABLA: devices
        # ====================================================================
        # Almacena los dispositivos físicos en el bus Modbus (por unit_id).
        # Cada dispositivo puede tener múltiples capabilities (MPU6050, Wind, Load).
        # Usada por:
        #   - DeviceManager: caché de dispositivos descubiertos
        #   - Bridge ThingsBoard: mapeo unit_id → ThingsBoard Device
        # ====================================================================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                unit_id INTEGER PRIMARY KEY,         -- Modbus Unit ID (1..247)
                alias TEXT,                          -- Nombre amigable: "PA_L", "WindMeter"
                vendor_code TEXT,                    -- Código de fabricante (0x4C6F = Lobo)
                capabilities TEXT NOT NULL,          -- JSON array: ["MPU6050", "Wind", "Load"]
                rig_id TEXT NOT NULL,                -- Estructura/ubicación: "RIG_01", "TOWER_A"
                firmware_version TEXT,               -- Versión firmware (ej: "v2.1.3")
                created_at TEXT NOT NULL,            -- Timestamp ISO8601 de discovery
                last_seen TEXT NOT NULL,             -- Última telemetría exitosa
                enabled INTEGER NOT NULL DEFAULT 1,  -- 1=activo, 0=deshabilitado
                
                CHECK (enabled IN (0, 1)),
                CHECK (unit_id BETWEEN 1 AND 247)
            )
        """)
        logger.info("✅ Tabla 'devices' creada/verificada")
        
        # ====================================================================
        # TABLA: sensors
        # ====================================================================
        # Almacena los sensores lógicos que pertenecen a cada dispositivo.
        # Un dispositivo con MPU6050+Wind tendrá múltiples sensores:
        #   UNIT_2_TILT_X, UNIT_2_TILT_Y, UNIT_2_TEMP, UNIT_2_WIND_SPEED, etc.
        # Usada por:
        #   - PollingService: para saber qué magnitudes guardar en BD
        #   - Motor de alertas: para obtener umbrales alarm_lo/alarm_hi
        #   - Bridge ThingsBoard: mapeo sensor_id → telemetría keys
        # ====================================================================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sensors (
                sensor_id TEXT PRIMARY KEY,          -- ID lógico: "UNIT_1_TILT_X", "UNIT_2_WIND_SPEED"
                unit_id INTEGER NOT NULL,            -- Dispositivo padre
                type TEXT NOT NULL,                  -- Tipo: "tilt", "wind", "temperature", "acceleration"
                register INTEGER NOT NULL,           -- Registro Modbus de lectura principal
                unit TEXT NOT NULL,                  -- Unidad física: "deg", "m/s", "kg", "g", "celsius"
                alarm_lo REAL,                       -- Umbral inferior de alarma (NULL si no aplica)
                alarm_hi REAL,                       -- Umbral superior de alarma (NULL si no aplica)
                created_at TEXT NOT NULL,            -- Timestamp ISO8601 de alta
                enabled INTEGER NOT NULL DEFAULT 1,  -- 1=activo, 0=deshabilitado
                
                FOREIGN KEY (unit_id) REFERENCES devices(unit_id) ON DELETE CASCADE,
                CHECK (enabled IN (0, 1))
            )
        """)
        logger.info("✅ Tabla 'sensors' creada/verificada")
        
        # ====================================================================
        # TABLA: measurements
        # ====================================================================
        # Serie temporal de telemetría. Cada fila = una medida de un sensor.
        # Usada por:
        #   - PollingService: inserta lecturas en cada ciclo de polling
        #   - Motor de alertas: consulta valores recientes vs umbrales
        #   - Bridge ThingsBoard: lee medidas no sincronizadas (sent_to_cloud=0)
        #     y las publica como telemetría agregada a ThingsBoard
        # ====================================================================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS measurements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,                 -- ISO8601 UTC: "2025-12-03T10:15:30Z"
                sensor_id TEXT NOT NULL,                 -- Ref a sensors.sensor_id
                type TEXT NOT NULL,                      -- Redundante: "tilt", "wind", "load"
                value REAL NOT NULL,                     -- Valor numérico de la medida
                unit TEXT NOT NULL,                      -- Unidad: "deg", "m_s", "kg", "g"
                quality TEXT NOT NULL DEFAULT 'OK',      -- Estado: OK, WARN, ALARM, ERROR_COMMS
                sent_to_cloud INTEGER NOT NULL DEFAULT 0,-- 0=pendiente, 1=ya enviado a ThingsBoard
                
                FOREIGN KEY (sensor_id) REFERENCES sensors(sensor_id),
                CHECK (quality IN ('OK', 'WARN', 'ALARM', 'ERROR_COMMS')),
                CHECK (sent_to_cloud IN (0, 1))
            )
        """)
        logger.info("✅ Tabla 'measurements' creada/verificada")
        
        # Índices para optimizar consultas frecuentes:
        # - idx_measurements_timestamp: Consultas por rango de tiempo
        # - idx_measurements_sensor_id: Consultas por sensor específico
        # - idx_measurements_sent: Bridge ThingsBoard busca sent_to_cloud=0
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_measurements_timestamp 
            ON measurements(timestamp)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_measurements_sensor_id 
            ON measurements(sensor_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_measurements_sent 
            ON measurements(sent_to_cloud)
        """)
        logger.info("✅ Índices de 'measurements' creados/verificados")
        
        # Índice para sensors por unit_id (consultas de sensores de un dispositivo)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_sensors_unit_id 
            ON sensors(unit_id)
        """)
        
        # ====================================================================
        # TABLA: alerts
        # ====================================================================
        # Alertas generadas localmente en el Edge cuando se detectan anomalías.
        # Usada por:
        #   - Motor de alertas: inserta nuevas alertas al detectar violaciones de umbrales
        #   - Dashboard local: muestra alertas activas (ack=0)
        #   - Bridge ThingsBoard: puede publicar alertas como atributos o alarmas
        # ====================================================================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,                      -- ISO8601 UTC de generación
                sensor_id TEXT,                               -- Sensor afectado (NULL si es alerta de sistema)
                rig_id TEXT,                                  -- Rig afectado (NULL si no aplica)
                level TEXT NOT NULL,                          -- Nivel: INFO, WARN, ALARM, CRITICAL
                code TEXT NOT NULL,                           -- Código: "TILT_LIMIT_EXCEEDED", "COMMS_TIMEOUT"
                message TEXT NOT NULL,                        -- Descripción legible para operadores
                ack INTEGER NOT NULL DEFAULT 0,               -- 0=no reconocida, 1=reconocida
                
                FOREIGN KEY (sensor_id) REFERENCES sensors(sensor_id),
                CHECK (level IN ('INFO', 'WARN', 'ALARM', 'CRITICAL')),
                CHECK (ack IN (0, 1))
            )
        """)
        logger.info("✅ Tabla 'alerts' creada/verificadas")
        
        # Índice para consultar alertas no reconocidas
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_alerts_ack 
            ON alerts(ack)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_alerts_timestamp 
            ON alerts(timestamp)
        """)
        logger.info("✅ Índices de 'alerts' creados/verificados")
        
        # ====================================================================
        # COMMIT Y CIERRE
        # ====================================================================
        conn.commit()
        logger.info("💾 Esquema de BD inicializado correctamente")
        
    except sqlite3.Error as e:
        conn.rollback()
        logger.error(f"❌ Error al inicializar BD: {e}")
        raise
    
    finally:
        conn.close()
        logger.info("🔌 Conexión a BD cerrada")


# ============================================================================
# CLASE DATABASE - API DE ACCESO A DATOS
# ============================================================================

class Database:
    """
    Gestor de base de datos SQLite para el Edge Layer.
    Provee métodos CRUD para sensors, measurements, alerts.
    """
    
    def __init__(self, db_path: str = DB_PATH):
        """
        Inicializa el gestor de BD.
        
        Args:
            db_path: Ruta al archivo SQLite
        """
        self.db_path = db_path
        
        # Asegurar que el esquema esté creado
        init_db(self.db_path)
        
        logger.info(f"✅ Database inicializado: {self.db_path}")
    
    @contextmanager
    def _get_connection(self):
        """Context manager para conexiones SQLite"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    # ========================================================================
    # OPERACIONES CON DEVICES
    # ========================================================================
    
    def upsert_device(self, device_data: Dict[str, Any]) -> None:
        """
        Inserta o actualiza un dispositivo.
        
        Args:
            device_data: Dict con campos de la tabla devices
                Obligatorios: unit_id, capabilities, rig_id
                Opcionales: alias, vendor_code, firmware_version, enabled
        
        Example:
            db.upsert_device({
                'unit_id': 2,
                'alias': 'PA_L',
                'vendor_code': '0x4C6F',
                'capabilities': '["MPU6050", "Wind"]',
                'rig_id': 'RIG_01',
                'firmware_version': 'v2.1.0',
                'enabled': 1
            })
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Verificar si ya existe
            cursor.execute("SELECT unit_id FROM devices WHERE unit_id = ?", 
                         (device_data['unit_id'],))
            exists = cursor.fetchone() is not None
            
            timestamp_now = datetime.utcnow().isoformat() + 'Z'
            
            if exists:
                # UPDATE
                cursor.execute("""
                    UPDATE devices SET
                        alias = ?,
                        vendor_code = ?,
                        capabilities = ?,
                        rig_id = ?,
                        firmware_version = ?,
                        last_seen = ?,
                        enabled = ?
                    WHERE unit_id = ?
                """, (
                    device_data.get('alias'),
                    device_data.get('vendor_code'),
                    device_data['capabilities'],
                    device_data['rig_id'],
                    device_data.get('firmware_version'),
                    timestamp_now,
                    device_data.get('enabled', 1),
                    device_data['unit_id']
                ))
                logger.debug(f"Device unit_id={device_data['unit_id']} actualizado")
            else:
                # INSERT
                cursor.execute("""
                    INSERT INTO devices (
                        unit_id, alias, vendor_code, capabilities, rig_id,
                        firmware_version, created_at, last_seen, enabled
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    device_data['unit_id'],
                    device_data.get('alias'),
                    device_data.get('vendor_code'),
                    device_data['capabilities'],
                    device_data['rig_id'],
                    device_data.get('firmware_version'),
                    timestamp_now,
                    timestamp_now,
                    device_data.get('enabled', 1)
                ))
                logger.debug(f"Device unit_id={device_data['unit_id']} creado")
            
            conn.commit()
    
    def get_device(self, unit_id: int) -> Optional[Dict[str, Any]]:
        """
        Obtiene un dispositivo por unit_id.
        
        Args:
            unit_id: Modbus Unit ID
        
        Returns:
            Dict con datos del dispositivo o None si no existe
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM devices WHERE unit_id = ?", (unit_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_all_devices(self, enabled_only: bool = True) -> List[Dict[str, Any]]:
        """
        Obtiene todos los dispositivos.
        
        Args:
            enabled_only: Si True, solo devuelve enabled=1
        
        Returns:
            Lista de dicts con datos de dispositivos
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if enabled_only:
                cursor.execute("SELECT * FROM devices WHERE enabled = 1 ORDER BY unit_id")
            else:
                cursor.execute("SELECT * FROM devices ORDER BY unit_id")
            return [dict(row) for row in cursor.fetchall()]
    
    def update_device_last_seen(self, unit_id: int) -> None:
        """
        Actualiza el timestamp last_seen de un dispositivo.
        
        Args:
            unit_id: Modbus Unit ID
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            timestamp_now = datetime.utcnow().isoformat() + 'Z'
            cursor.execute("""
                UPDATE devices SET last_seen = ? WHERE unit_id = ?
            """, (timestamp_now, unit_id))
            conn.commit()
    
    # ========================================================================
    # OPERACIONES CON SENSORS
    # ========================================================================
    
    def upsert_sensor(self, sensor_data: Dict[str, Any]) -> None:
        """
        Inserta o actualiza un sensor.
        
        Args:
            sensor_data: Dict con campos de la tabla sensors
                Obligatorios: sensor_id, unit_id, type, register, unit
                Opcionales: alarm_lo, alarm_hi, enabled
        
        Example:
            db.upsert_sensor({
                'sensor_id': 'UNIT_2_TILT_X',
                'unit_id': 2,
                'type': 'tilt',
                'register': 0,
                'unit': 'deg',
                'alarm_lo': -10.0,
                'alarm_hi': 10.0,
                'enabled': 1
            })
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Verificar si ya existe
            cursor.execute("SELECT sensor_id FROM sensors WHERE sensor_id = ?", 
                         (sensor_data['sensor_id'],))
            exists = cursor.fetchone() is not None
            
            if exists:
                # UPDATE
                cursor.execute("""
                    UPDATE sensors SET
                        unit_id = ?,
                        type = ?,
                        register = ?,
                        unit = ?,
                        alarm_lo = ?,
                        alarm_hi = ?,
                        enabled = ?
                    WHERE sensor_id = ?
                """, (
                    sensor_data['unit_id'],
                    sensor_data['type'],
                    sensor_data['register'],
                    sensor_data['unit'],
                    sensor_data.get('alarm_lo'),
                    sensor_data.get('alarm_hi'),
                    sensor_data.get('enabled', 1),
                    sensor_data['sensor_id']
                ))
                logger.debug(f"Sensor '{sensor_data['sensor_id']}' actualizado")
            else:
                # INSERT
                cursor.execute("""
                    INSERT INTO sensors (
                        sensor_id, unit_id, type, register,
                        unit, alarm_lo, alarm_hi, created_at, enabled
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    sensor_data['sensor_id'],
                    sensor_data['unit_id'],
                    sensor_data['type'],
                    sensor_data['register'],
                    sensor_data['unit'],
                    sensor_data.get('alarm_lo'),
                    sensor_data.get('alarm_hi'),
                    datetime.utcnow().isoformat() + 'Z',
                    sensor_data.get('enabled', 1)
                ))
                logger.debug(f"Sensor '{sensor_data['sensor_id']}' creado")
            
            conn.commit()
    
    def get_sensor(self, sensor_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene un sensor por ID.
        
        Args:
            sensor_id: ID del sensor
        
        Returns:
            Dict con datos del sensor o None si no existe
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sensors WHERE sensor_id = ?", (sensor_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_all_sensors(self, enabled_only: bool = True) -> List[Dict[str, Any]]:
        """
        Obtiene todos los sensores.
        
        Args:
            enabled_only: Si True, solo sensores con enabled=1
        
        Returns:
            Lista de sensores
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if enabled_only:
                cursor.execute("SELECT * FROM sensors WHERE enabled = 1 ORDER BY unit_id, sensor_id")
            else:
                cursor.execute("SELECT * FROM sensors ORDER BY unit_id, sensor_id")
            return [dict(row) for row in cursor.fetchall()]
    
    def get_sensors_by_device(self, unit_id: int, enabled_only: bool = True) -> List[Dict[str, Any]]:
        """
        Obtiene todos los sensores de un dispositivo específico.
        
        Args:
            unit_id: Modbus Unit ID del dispositivo
            enabled_only: Si True, solo sensores con enabled=1
        
        Returns:
            Lista de sensores del dispositivo
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if enabled_only:
                cursor.execute("""
                    SELECT * FROM sensors 
                    WHERE unit_id = ? AND enabled = 1 
                    ORDER BY sensor_id
                """, (unit_id,))
            else:
                cursor.execute("""
                    SELECT * FROM sensors 
                    WHERE unit_id = ? 
                    ORDER BY sensor_id
                """, (unit_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    # ========================================================================
    # OPERACIONES CON MEASUREMENTS
    # ========================================================================
    
    def insert_measurement(self, measurement: Dict[str, Any]) -> int:
        """
        Inserta una medida de telemetría.
        
        Args:
            measurement: Dict con campos:
                - sensor_id (str)
                - type (str): "tilt", "wind", "load"
                - value (float)
                - unit (str): "deg", "m_s", "kg", "g"
                - quality (str, optional): "OK" por defecto
                - timestamp (datetime, optional): datetime.utcnow() por defecto
        
        Returns:
            ID del registro insertado
        
        Example:
            db.insert_measurement({
                'sensor_id': 'TILT_01',
                'type': 'tilt',
                'value': 2.35,
                'unit': 'deg',
                'quality': 'OK'
            })
        """
        timestamp = measurement.get('timestamp', datetime.utcnow())
        if isinstance(timestamp, datetime):
            timestamp = timestamp.isoformat() + 'Z'
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO measurements (
                    timestamp, sensor_id, type, value, unit, quality, sent_to_cloud
                ) VALUES (?, ?, ?, ?, ?, ?, 0)
            """, (
                timestamp,
                measurement['sensor_id'],
                measurement['type'],
                measurement['value'],
                measurement['unit'],
                measurement.get('quality', 'OK')
            ))
            conn.commit()
            return cursor.lastrowid
    
    def get_measurements(
        self, 
        sensor_id: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Consulta medidas con filtros opcionales.
        
        Args:
            sensor_id: Filtrar por sensor (opcional)
            since: Timestamp desde (opcional)
            limit: Máximo número de registros
        
        Returns:
            Lista de medidas (más recientes primero)
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            query = "SELECT * FROM measurements WHERE 1=1"
            params = []
            
            if sensor_id:
                query += " AND sensor_id = ?"
                params.append(sensor_id)
            
            if since:
                since_str = since.isoformat() + 'Z'
                query += " AND timestamp >= ?"
                params.append(since_str)
            
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def mark_as_sent(self, measurement_ids: List[int]) -> None:
        """
        Marca medidas como enviadas a ThingsBoard.
        
        Args:
            measurement_ids: Lista de IDs de measurements
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            placeholders = ','.join('?' * len(measurement_ids))
            cursor.execute(f"""
                UPDATE measurements 
                SET sent_to_cloud = 1 
                WHERE id IN ({placeholders})
            """, measurement_ids)
            conn.commit()
            logger.debug(f"Marcadas {len(measurement_ids)} medidas como enviadas")
    
    def get_unsent_measurements(self, limit: int = 1000) -> List[Dict[str, Any]]:
        """
        Obtiene medidas pendientes de enviar a ThingsBoard.
        
        Args:
            limit: Máximo número de registros
        
        Returns:
            Lista de medidas con sent_to_cloud=0
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM measurements 
                WHERE sent_to_cloud = 0 
                ORDER BY timestamp ASC 
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]
    
    # ========================================================================
    # OPERACIONES CON ALERTS
    # ========================================================================
    
    def insert_alert(self, alert: Dict[str, Any]) -> int:
        """
        Inserta una alerta.
        
        Args:
            alert: Dict con campos:
                - level (str): "INFO", "WARN", "ALARM", "CRITICAL"
                - code (str): Código de alerta
                - message (str): Descripción
                - sensor_id (str, optional)
                - rig_id (str, optional)
                - timestamp (datetime, optional)
        
        Returns:
            ID de la alerta insertada
        
        Example:
            db.insert_alert({
                'level': 'ALARM',
                'code': 'TILT_LIMIT_EXCEEDED',
                'message': 'Inclinación de 5.2° supera umbral de 5.0°',
                'sensor_id': 'TILT_01',
                'rig_id': 'RIG_01'
            })
        """
        timestamp = alert.get('timestamp', datetime.utcnow())
        if isinstance(timestamp, datetime):
            timestamp = timestamp.isoformat() + 'Z'
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO alerts (
                    timestamp, sensor_id, rig_id, level, code, message, ack
                ) VALUES (?, ?, ?, ?, ?, ?, 0)
            """, (
                timestamp,
                alert.get('sensor_id'),
                alert.get('rig_id'),
                alert['level'],
                alert['code'],
                alert['message']
            ))
            conn.commit()
            return cursor.lastrowid
    
    def get_alerts(
        self, 
        ack: Optional[bool] = None,
        level: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Consulta alertas con filtros.
        
        Args:
            ack: None=todas, True=reconocidas, False=no reconocidas
            level: Filtrar por nivel (opcional)
            limit: Máximo número de alertas
        
        Returns:
            Lista de alertas (más recientes primero)
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            query = "SELECT * FROM alerts WHERE 1=1"
            params = []
            
            if ack is not None:
                query += " AND ack = ?"
                params.append(1 if ack else 0)
            
            if level:
                query += " AND level = ?"
                params.append(level)
            
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def acknowledge_alert(self, alert_id: int) -> None:
        """
        Marca una alerta como reconocida.
        
        Args:
            alert_id: ID de la alerta
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE alerts SET ack = 1 WHERE id = ?", (alert_id,))
            conn.commit()
            logger.debug(f"Alerta {alert_id} reconocida")
    
    # ========================================================================
    # MANTENIMIENTO
    # ========================================================================
    
    def cleanup_old_data(self, days: int = DEFAULT_RETENTION_DAYS) -> int:
        """
        Elimina medidas antiguas para liberar espacio.
        
        Args:
            days: Retención en días (elimina medidas más antiguas)
        
        Returns:
            Número de registros eliminados
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        cutoff_str = cutoff.isoformat() + 'Z'
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM measurements 
                WHERE timestamp < ?
            """, (cutoff_str,))
            deleted = cursor.rowcount
            conn.commit()
            
            # VACUUM para recuperar espacio
            cursor.execute("VACUUM")
            
            logger.info(f"🗑️ Eliminadas {deleted} medidas anteriores a {cutoff_str}")
            return deleted
    
    def get_db_stats(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas de la BD.
        
        Returns:
            Dict con stats: tamaño, conteos, etc.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Contar registros
            cursor.execute("SELECT COUNT(*) FROM devices")
            device_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM sensors")
            sensor_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM measurements")
            measurement_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM alerts")
            alert_count = cursor.fetchone()[0]
            
            # Tamaño del archivo
            db_size_bytes = os.path.getsize(self.db_path)
            db_size_mb = db_size_bytes / (1024 * 1024)
            
            return {
                'db_path': self.db_path,
                'db_size_mb': round(db_size_mb, 2),
                'device_count': device_count,
                'sensor_count': sensor_count,
                'measurement_count': measurement_count,
                'alert_count': alert_count
            }


# ============================================================================
# SCRIPT DE INICIALIZACIÓN STANDALONE
# ============================================================================

if __name__ == '__main__':
    """
    Script de inicialización standalone.
    Uso:
        python database.py
        python database.py /custom/path/to/measurements.db
    """
    import sys
    
    # Permitir ruta custom como argumento
    custom_path = sys.argv[1] if len(sys.argv) > 1 else DB_PATH
    
    print(f"Inicializando base de datos: {custom_path}")
    init_db(custom_path)
    
    # Verificar creación
    db = Database(custom_path)
    stats = db.get_db_stats()
    print(f"\n✅ Base de datos inicializada correctamente:")
    print(f"   Ruta: {stats['db_path']}")
    print(f"   Tamaño: {stats['db_size_mb']} MB")
    print(f"   Sensores: {stats['sensor_count']}")
    print(f"   Medidas: {stats['measurement_count']}")
    print(f"   Alertas: {stats['alert_count']}")
