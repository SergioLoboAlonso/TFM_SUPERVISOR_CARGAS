"""
MQTT Bridge Service
===================

Servicio que publica medidas y alertas a broker MQTT para integración con plataformas IoT.

Estructura de topics:
--------------------
- Medidas: edge/{device_id}/{sensor_type}/measurements
  Ejemplo: edge/unit_2/tilt/measurements
           edge/unit_1/wind/measurements

- Alertas: edge/{device_id}/alerts
  Ejemplo: edge/unit_2/alerts
           edge/system/alerts

Payload JSON:
-------------
Medidas:
{
    "timestamp": "2025-12-03T20:30:00.123456Z",
    "device_id": "unit_2",
    "sensor_id": "UNIT_2_TILT_X",
    "sensor_type": "tilt",
    "value": 2.5,
    "unit": "deg",
    "quality": "GOOD"
}

Alertas:
{
    "timestamp": "2025-12-03T20:30:00.123456Z",
    "alert_id": 123,
    "device_id": "unit_2",
    "sensor_id": "UNIT_2_TILT_X",
    "level": "ALARM",
    "code": "THRESHOLD_EXCEEDED_HI",
    "message": "Sensor UNIT_2_TILT_X: valor 6.2 deg supera umbral...",
    "ack": false
}

Author: Sergio Lobo
Date: 2025-12-03
"""

import json
import time
import threading
from typing import Dict, Any, Optional, List
from datetime import datetime

try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False

from logger import logger
from config import Config


class MQTTBridge:
    """
    Puente MQTT para publicar medidas y alertas a plataformas IoT.
    """
    
    def __init__(self, database, enabled: bool = None):
        """
        Inicializa el puente MQTT.
        
        Args:
            database: Instancia de Database para consultar datos
            enabled: Si es None, se habilita solo si hay configuración MQTT válida
        """
        self.db = database
        self.client: Optional[mqtt.Client] = None
        self.connected = False
        self._lock = threading.Lock()
        
        # Determinar si MQTT está habilitado
        if enabled is None:
            self.enabled = (
                MQTT_AVAILABLE and 
                Config.MQTT_BROKER_HOST is not None and 
                Config.MQTT_BROKER_HOST.strip() != ''
            )
        else:
            self.enabled = enabled and MQTT_AVAILABLE
        
        if not self.enabled:
            if not MQTT_AVAILABLE:
                logger.warning("⚠️  Librería paho-mqtt no instalada. Puente MQTT deshabilitado")
            else:
                logger.info("ℹ️  MQTT no configurado en .env. Puente MQTT deshabilitado")
            return
        
        # Configuración
        self.broker_host = Config.MQTT_BROKER_HOST
        self.broker_port = Config.MQTT_BROKER_PORT
        self.username = Config.MQTT_USERNAME
        self.password = Config.MQTT_PASSWORD
        self.qos = Config.MQTT_QOS
        self.topic_prefix = Config.MQTT_TOPIC_PREFIX or "edge"
        
        # Inicializar cliente MQTT
        self._init_client()
        
        logger.info(f"🌐 MQTTBridge inicializado (broker: {self.broker_host}:{self.broker_port})")
    
    
    def _init_client(self):
        """Inicializa el cliente MQTT y configura callbacks."""
        try:
            self.client = mqtt.Client(client_id=f"edge_supervisor_{int(time.time())}")
            
            # Configurar credenciales si existen
            if self.username and self.password:
                self.client.username_pw_set(self.username, self.password)
            
            # Callbacks
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_publish = self._on_publish
            
            # Conectar al broker
            self.client.connect_async(self.broker_host, self.broker_port, keepalive=60)
            self.client.loop_start()
            
        except Exception as e:
            logger.error(f"❌ Error al inicializar cliente MQTT: {e}", exc_info=True)
            self.enabled = False
    
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback cuando se conecta al broker."""
        if rc == 0:
            self.connected = True
            logger.info(f"✅ Conectado a broker MQTT {self.broker_host}:{self.broker_port}")
        else:
            self.connected = False
            logger.error(f"❌ Error de conexión MQTT (código {rc})")
    
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback cuando se desconecta del broker."""
        self.connected = False
        if rc != 0:
            logger.warning(f"⚠️  Desconexión inesperada de MQTT (código {rc}). Reintentando...")
    
    
    def _on_publish(self, client, userdata, mid):
        """Callback cuando se publica un mensaje."""
        logger.debug(f"📤 Mensaje MQTT publicado (mid: {mid})")
    
    
    def publish_measurement(
        self,
        device_id: str,
        sensor_id: str,
        sensor_type: str,
        value: float,
        unit: str,
        timestamp: Optional[str] = None,
        quality: str = "GOOD"
    ) -> bool:
        """
        Publica una medida al broker MQTT.
        
        Args:
            device_id: ID del dispositivo (ej: "unit_2")
            sensor_id: ID del sensor (ej: "UNIT_2_TILT_X")
            sensor_type: Tipo de sensor (ej: "tilt", "wind", "temperature")
            value: Valor medido
            unit: Unidad de medida
            timestamp: ISO8601 timestamp (opcional, se genera si no se provee)
            quality: Calidad de la medida (GOOD, BAD, UNCERTAIN)
        
        Returns:
            True si se publicó correctamente, False en caso contrario
        """
        if not self.enabled or not self.connected:
            return False
        
        try:
            # Preparar payload
            payload = {
                "timestamp": timestamp or datetime.utcnow().isoformat() + 'Z',
                "device_id": device_id,
                "sensor_id": sensor_id,
                "sensor_type": sensor_type,
                "value": value,
                "unit": unit,
                "quality": quality
            }
            
            # Topic: edge/{device_id}/{sensor_type}/measurements
            topic = f"{self.topic_prefix}/{device_id}/{sensor_type}/measurements"
            
            # Publicar
            result = self.client.publish(topic, json.dumps(payload), qos=self.qos)
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.debug(f"📤 Medida publicada: {topic} -> {value} {unit}")
                return True
            else:
                logger.warning(f"⚠️  Error al publicar medida en {topic}: rc={result.rc}")
                return False
        
        except Exception as e:
            logger.error(f"❌ Error al publicar medida: {e}", exc_info=True)
            return False
    
    
    def publish_alert(
        self,
        alert_id: int,
        level: str,
        code: str,
        message: str,
        device_id: Optional[str] = None,
        sensor_id: Optional[str] = None,
        timestamp: Optional[str] = None,
        ack: bool = False
    ) -> bool:
        """
        Publica una alerta al broker MQTT.
        
        Args:
            alert_id: ID de la alerta
            level: Nivel (INFO, WARN, ALARM, CRITICAL)
            code: Código de alerta
            message: Mensaje descriptivo
            device_id: ID del dispositivo (ej: "unit_2", "system")
            sensor_id: ID del sensor (opcional)
            timestamp: ISO8601 timestamp
            ack: Si la alerta está reconocida
        
        Returns:
            True si se publicó correctamente
        """
        if not self.enabled or not self.connected:
            return False
        
        try:
            # Preparar payload
            payload = {
                "timestamp": timestamp or datetime.utcnow().isoformat() + 'Z',
                "alert_id": alert_id,
                "level": level,
                "code": code,
                "message": message,
                "ack": ack
            }
            
            if device_id:
                payload["device_id"] = device_id
            if sensor_id:
                payload["sensor_id"] = sensor_id
            
            # Topic: edge/{device_id}/alerts
            device = device_id or "system"
            topic = f"{self.topic_prefix}/{device}/alerts"
            
            # Publicar
            result = self.client.publish(topic, json.dumps(payload), qos=self.qos)
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.debug(f"📤 Alerta publicada: {topic} -> {code} ({level})")
                return True
            else:
                logger.warning(f"⚠️  Error al publicar alerta en {topic}: rc={result.rc}")
                return False
        
        except Exception as e:
            logger.error(f"❌ Error al publicar alerta: {e}", exc_info=True)
            return False
    
    
    def publish_batch_measurements(self, measurements: List[Dict[str, Any]]) -> int:
        """
        Publica múltiples medidas en batch.
        
        Args:
            measurements: Lista de dicts con campos para publish_measurement()
        
        Returns:
            Número de medidas publicadas exitosamente
        """
        if not self.enabled or not self.connected:
            return 0
        
        success_count = 0
        for m in measurements:
            if self.publish_measurement(**m):
                success_count += 1
        
        return success_count
    
    
    def disconnect(self):
        """Desconecta del broker MQTT de forma limpia."""
        if self.client and self.connected:
            logger.info("🔌 Desconectando de broker MQTT...")
            self.client.loop_stop()
            self.client.disconnect()
            self.connected = False
    
    
    def __del__(self):
        """Destructor: asegura desconexión limpia."""
        self.disconnect()
