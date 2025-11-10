"""
Configuración global del Edge Layer.
Carga variables de entorno desde .env y expone settings.
"""
import os
import logging
from dotenv import load_dotenv
from pathlib import Path

# Cargar .env desde el directorio edge/
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)


class Config:
    """Configuración del Edge Layer"""
    
    # Modbus RTU
    MODBUS_PORT = os.getenv('MODBUS_PORT')
    MODBUS_BAUDRATE = int(os.getenv('MODBUS_BAUDRATE', '115200'))
    MODBUS_TIMEOUT = float(os.getenv('MODBUS_TIMEOUT', '0.3'))  # Timeout normal para operaciones
    MODBUS_DISCOVERY_TIMEOUT = float(os.getenv('MODBUS_DISCOVERY_TIMEOUT', '0.08'))  # 80ms - Balance óptimo velocidad/robustez
    
    # Discovery
    DEVICE_UNIT_ID_MIN = int(os.getenv('DEVICE_UNIT_ID_MIN', '1'))
    DEVICE_UNIT_ID_MAX = int(os.getenv('DEVICE_UNIT_ID_MAX', '10'))
    DISCOVERY_RETRY_ON_FOUND = False  # No reintentar cuando se encuentre un dispositivo
    DISCOVERY_BATCH_SIZE = int(os.getenv('DISCOVERY_BATCH_SIZE', '20'))  # Escanear a lo sumo 20 unit IDs por tanda
    
    # Polling
    POLL_INTERVAL_SEC = float(os.getenv('POLL_INTERVAL_SEC', '2.0'))
    INTER_FRAME_DELAY_MS = int(os.getenv('INTER_FRAME_DELAY_MS', '15'))  # Aumentado a 15ms para dar margen al Micro (32U4)
    MAX_POLL_DEVICES = int(os.getenv('MAX_POLL_DEVICES', '20'))  # Máximo de dispositivos monitorizados simultáneamente
    PER_DEVICE_REFRESH_SEC = float(os.getenv('PER_DEVICE_REFRESH_SEC', '1.0'))  # Objetivo de refresco por dispositivo
    OFFLINE_BACKOFF_SEC = float(os.getenv('OFFLINE_BACKOFF_SEC', '5.0'))  # Backoff base al marcar offline
    OFFLINE_BACKOFF_MAX_SEC = float(os.getenv('OFFLINE_BACKOFF_MAX_SEC', '60.0'))  # Límite superior backoff adaptativo
    
    # Flask
    FLASK_HOST = os.getenv('FLASK_HOST', '0.0.0.0')
    FLASK_PORT = int(os.getenv('FLASK_PORT', '8080'))
    FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'True').lower() in ('true', '1', 'yes')
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()  # INFO para producción, DEBUG para desarrollo
    LOG_FILE = os.getenv('LOG_FILE', 'edge.log')
    
    # MQTT (opcional)
    MQTT_BROKER_HOST = os.getenv('MQTT_BROKER_HOST')
    MQTT_BROKER_PORT = int(os.getenv('MQTT_BROKER_PORT', '1883'))
    MQTT_USERNAME = os.getenv('MQTT_USERNAME')
    MQTT_PASSWORD = os.getenv('MQTT_PASSWORD')
    MQTT_QOS = int(os.getenv('MQTT_QOS', '1'))
    MQTT_TOPIC_PREFIX = os.getenv('MQTT_TOPIC_PREFIX', 'tfm/devices')
    
    @classmethod
    def validate(cls):
        """Valida la configuración crítica"""
        errors = []
        
        # Validar puerto serie
        if not cls.MODBUS_PORT:
            errors.append("MODBUS_PORT no configurado en .env (requerido)")
        elif not cls.MODBUS_PORT.startswith('/dev/'):
            logging.warning(f"Puerto serie no parece válido: {cls.MODBUS_PORT}")
        
        if cls.DEVICE_UNIT_ID_MIN < 1 or cls.DEVICE_UNIT_ID_MIN > 247:
            errors.append(f"DEVICE_UNIT_ID_MIN debe estar entre 1 y 247 (actual: {cls.DEVICE_UNIT_ID_MIN})")
        
        if cls.DEVICE_UNIT_ID_MAX < 1 or cls.DEVICE_UNIT_ID_MAX > 247:
            errors.append(f"DEVICE_UNIT_ID_MAX debe estar entre 1 y 247 (actual: {cls.DEVICE_UNIT_ID_MAX})")
        
        if cls.DEVICE_UNIT_ID_MIN > cls.DEVICE_UNIT_ID_MAX:
            errors.append(f"DEVICE_UNIT_ID_MIN ({cls.DEVICE_UNIT_ID_MIN}) debe ser <= DEVICE_UNIT_ID_MAX ({cls.DEVICE_UNIT_ID_MAX})")
        
        if cls.MODBUS_BAUDRATE not in (9600, 19200, 38400, 57600, 115200):
            logging.warning(f"Baudrate no estándar: {cls.MODBUS_BAUDRATE}")
        
        if errors:
            raise ValueError("Errores de configuración:\n" + "\n".join(f"  - {e}" for e in errors))
        
        return True


# Validar al importar
Config.validate()
