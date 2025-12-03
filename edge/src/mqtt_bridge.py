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
        
        # Detectar si es ThingsBoard
        self.is_thingsboard = (
            self.topic_prefix.startswith('v1/devices/me') or
            self.topic_prefix.startswith('v1/gateway') or
            'thingsboard' in self.broker_host.lower()
        )
        
        # Cache de medidas para batch (ThingsBoard)
        self._measurement_cache = {}  # {device_id: {sensor_key: value}}
        self._last_publish_time = {}
        self._batch_interval = 1.0  # segundos
        
        # Cache de dispositivos cuyos atributos ya fueron publicados
        self._published_attributes = set()
        
        # Inicializar cliente MQTT
        self._init_client()
        
        mode = "ThingsBoard" if self.is_thingsboard else "MQTT estándar"
        logger.info(f"🌐 MQTTBridge inicializado (broker: {self.broker_host}:{self.broker_port}, modo: {mode})")
    
    
    def _init_client(self):
        """Inicializa el cliente MQTT y configura callbacks."""
        try:
            self.client = mqtt.Client(client_id=f"edge_supervisor_{int(time.time())}")
            
            # Configurar credenciales
            # ThingsBoard usa el access token como username, sin password
            if self.username:
                password = self.password if self.password else None
                self.client.username_pw_set(self.username, password)
            
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
        quality: str = "GOOD",
        extra_keys: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Publica una medida al broker MQTT.
        
        Soporta dos modos:
        - MQTT estándar: edge/{device_id}/{sensor_type}/measurements
        - ThingsBoard: v1/devices/me/telemetry (batch de todas las medidas)
        
        Args:
            device_id: ID del dispositivo (ej: "unit_2")
            sensor_id: ID del sensor (ej: "UNIT_2_TILT_X")
            sensor_type: Tipo de sensor (ej: "tilt", "wind", "temperature")
            value: Valor medido
            unit: Unidad de medida
            timestamp: ISO8601 timestamp (opcional, se genera si no se provee)
            quality: Calidad de la medida (GOOD, BAD, UNCERTAIN)
            extra_keys: Claves adicionales para enviar en el mismo mensaje (ej: diagnóstico)
        
        Returns:
            True si se publicó correctamente, False en caso contrario
        """
        if not self.enabled or not self.connected:
            return False
        
        try:
            if self.is_thingsboard:
                # Modo ThingsBoard: acumular medidas y publicar en batch
                return self._publish_measurement_thingsboard(sensor_id, value, timestamp, extra_keys)
            else:
                # Modo MQTT estándar
                return self._publish_measurement_standard(device_id, sensor_id, sensor_type, value, unit, timestamp, quality, extra_keys)
        
        except Exception as e:
            logger.error(f"❌ Error al publicar medida: {e}", exc_info=True)
            return False
    
    
    def _publish_measurement_standard(
        self,
        device_id: str,
        sensor_id: str,
        sensor_type: str,
        value: float,
        unit: str,
        timestamp: Optional[str],
        quality: str,
        extra_keys: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Publicación MQTT estándar."""
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
        
        # Agregar claves extra si existen (ej: diagnóstico)
        if extra_keys:
            payload.update(extra_keys)
        
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
    
    
    def _publish_measurement_thingsboard(
        self,
        sensor_id: str,
        value: float,
        timestamp: Optional[str],
        extra_keys: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Publicación para ThingsBoard Gateway.
        
        ThingsBoard Gateway API usa:
        - Topic: v1/gateway/telemetry
        - Payload: {
            "device_1": [{"ts": 1234567890, "values": {"temperature": 18.5}}],
            "device_2": [{"ts": 1234567890, "values": {"tilt_x": -0.5}}]
          }
        
        Soporta extra_keys para enviar múltiples métricas (ej: diagnóstico).
        
        Ref: https://thingsboard.io/docs/reference/gateway-mqtt-api/
        """
        # Extraer device_id y tipo de sensor del sensor_id
        # UNIT_2_TILT_X -> device: "Sensor_Unit2", key: "tilt_x"
        # GATEWAY_MODBUS_DIAG -> device: "RPI_EDGE", key: "diag_success_rate"
        
        if sensor_id.startswith('GATEWAY_'):
            # Diagnóstico agregado del Gateway
            device_name = Config.EDGE_GATEWAY_NAME  # "RPI_EDGE"
        else:
            # Dispositivos individuales
            parts = sensor_id.split('_')
            if len(parts) < 2:
                return False
            
            unit_id = parts[1]  # "2"
            device_name = f"Sensor_Unit{unit_id}"
        
        # Mapeo de tipo de sensor a clave ThingsBoard
        key_mapping = {
            'TILT_X': 'tilt_x',
            'TILT_Y': 'tilt_y',
            'TEMP': 'temperature',
            'WIND_SPEED': 'wind_speed',
            'WIND_DIR': 'wind_direction',
            'ACCEL': 'acceleration',
            'GYRO': 'gyroscope',
            'LOAD': 'load',
            'DIAG': 'diag_success_rate',  # Diagnóstico individual
            'MODBUS_DIAG': 'diag_success_rate'  # Diagnóstico agregado del Gateway
        }
        
        # Extraer tipo de sensor del sensor_id
        key = None
        for sensor_type, tb_key in key_mapping.items():
            if sensor_type in sensor_id:
                key = tb_key
                break
        
        if not key:
            logger.warning(f"⚠️  No se pudo mapear sensor_id '{sensor_id}' a ThingsBoard key")
            return False
        
        # Acumular en cache por dispositivo
        if device_name not in self._measurement_cache:
            self._measurement_cache[device_name] = {}
        
        self._measurement_cache[device_name][key] = value
        
        # Si hay extra_keys (ej: diagnóstico), agregarlos también
        if extra_keys:
            for extra_key, extra_value in extra_keys.items():
                self._measurement_cache[device_name][extra_key] = extra_value
        
        # Publicar si han pasado suficiente tiempo o tenemos varias medidas
        now = time.time()
        last_publish = self._last_publish_time.get(device_name, 0)
        
        if (now - last_publish) >= self._batch_interval or len(self._measurement_cache[device_name]) >= 4:
            return self._flush_thingsboard_gateway_cache(device_name, timestamp)
        
        return True
    
    
    def _flush_thingsboard_gateway_cache(self, device_name: str, timestamp: Optional[str] = None) -> bool:
        """Envía todas las medidas acumuladas a ThingsBoard Gateway."""
        if device_name not in self._measurement_cache or not self._measurement_cache[device_name]:
            return False
        
        try:
            # Topic de ThingsBoard Gateway
            topic = "v1/gateway/telemetry"
            
            # Timestamp en milisegundos
            if timestamp:
                from datetime import datetime
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                ts_ms = int(dt.timestamp() * 1000)
            else:
                ts_ms = int(time.time() * 1000)
            
            # Payload formato Gateway: {device_name: [{ts: ms, values: {...}}]}
            payload = {
                device_name: [{
                    "ts": ts_ms,
                    "values": self._measurement_cache[device_name].copy()
                }]
            }
            
            # Publicar
            result = self.client.publish(topic, json.dumps(payload), qos=self.qos)
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.debug(f"📤 ThingsBoard Gateway telemetry: {device_name} -> {payload[device_name][0]['values']}")
                self._measurement_cache[device_name] = {}
                self._last_publish_time[device_name] = time.time()
                return True
            else:
                logger.warning(f"⚠️  Error al publicar a ThingsBoard Gateway: rc={result.rc}")
                return False
        
        except Exception as e:
            logger.error(f"❌ Error al flush ThingsBoard Gateway cache: {e}", exc_info=True)
            return False
    
    
    def publish_device_attributes(
        self,
        device_name: str,
        attributes: Dict[str, Any]
    ) -> bool:
        """
        Publica atributos del dispositivo a ThingsBoard Gateway.
        
        Los atributos son metadatos que no cambian frecuentemente:
        - owner/alias del dispositivo
        - tipo de sensor
        - capabilities
        - versión firmware
        
        Args:
            device_name: Nombre del dispositivo en ThingsBoard (ej: "Sensor_Unit2")
            attributes: Dict con atributos {"owner": "WindMeter", "type": "tilt", ...}
        
        Returns:
            True si se publicó correctamente
        """
        if not self.enabled or not self.connected:
            return False
        
        if not self.is_thingsboard:
            return False  # Solo para ThingsBoard
        
        # Evitar publicar atributos múltiples veces
        if device_name in self._published_attributes:
            return True
        
        try:
            # Topic de atributos en ThingsBoard Gateway
            topic = "v1/gateway/attributes"
            
            # Payload: {device_name: {attribute_key: value, ...}}
            payload = {
                device_name: attributes
            }
            
            # Publicar
            result = self.client.publish(topic, json.dumps(payload), qos=self.qos)
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.info(f"📋 Atributos publicados para {device_name}: {attributes}")
                self._published_attributes.add(device_name)
                return True
            else:
                logger.warning(f"⚠️  Error al publicar atributos de {device_name}: rc={result.rc}")
                return False
        
        except Exception as e:
            logger.error(f"❌ Error al publicar atributos: {e}", exc_info=True)
            return False
    
    
    def publish_device_connectivity(
        self,
        device_name: str,
        connected: bool,
        timestamp: str = None
    ) -> bool:
        """
        Publica evento de conectividad de dispositivo a ThingsBoard.
        
        Permite que ThingsBoard sepa cuando un dispositivo se conecta/desconecta,
        útil para actualizar dashboards automáticamente.
        
        Args:
            device_name: Nombre del dispositivo en ThingsBoard (ej: "Sensor_Unit2")
            connected: True si conectado, False si desconectado
            timestamp: ISO8601 timestamp (usa now() si no se provee)
        
        Returns:
            True si se publicó correctamente
        """
        if not self.enabled or not self.connected:
            return False
        
        if not self.is_thingsboard:
            return False
        
        try:
            topic = "v1/gateway/connect" if connected else "v1/gateway/disconnect"
            
            # Payload: {device: device_name}
            payload = {"device": device_name}
            
            result = self.client.publish(topic, json.dumps(payload), qos=self.qos)
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                status = "✅ conectado" if connected else "❌ desconectado"
                logger.info(f"🔌 Dispositivo {device_name} {status}")
                return True
            else:
                logger.warning(f"⚠️  Error al publicar conectividad de {device_name}: rc={result.rc}")
                return False
        
        except Exception as e:
            logger.error(f"❌ Error al publicar conectividad: {e}", exc_info=True)
            return False
    
    
    def publish_active_sensors_list(
        self,
        devices_info: List[Dict[str, Any]]
    ) -> bool:
        """
        Publica lista completa de dispositivos y sensores activos.
        
        Útil para dashboards que necesitan conocer todos los sensores disponibles
        y actualizar widgets automáticamente.
        
        Args:
            devices_info: Lista de dicts con info de dispositivos:
                [
                    {
                        'unit_id': 1,
                        'alias': 'WindMeter',
                        'capabilities': ['Wind', 'Identify'],
                        'enabled': True,
                        'online': True,
                        'sensors': ['UNIT_1_WIND_SPEED', 'UNIT_1_WIND_DIR']
                    },
                    ...
                ]
        
        Returns:
            True si se publicó correctamente
        """
        if not self.enabled or not self.connected:
            return False
        
        try:
            # Publicar inventario global como atributo del servidor Edge
            # Esto permite consultas desde ThingsBoard para auto-configurar widgets
            
            # Construir payload con lista de todos los dispositivos activos
            active_devices = []
            all_sensors = []
            
            for dev in devices_info:
                if dev.get('enabled', True):
                    device_name = f"Sensor_Unit{dev['unit_id']}"
                    active_devices.append({
                        'name': device_name,
                        'alias': dev.get('alias', f"Unit_{dev['unit_id']}"),
                        'unit_id': dev['unit_id'],
                        'capabilities': dev.get('capabilities', []),
                        'online': dev.get('online', False)
                    })
                    
                    # Agregar sensores individuales
                    for sensor_id in dev.get('sensors', []):
                        all_sensors.append({
                            'sensor_id': sensor_id,
                            'device': device_name,
                            'unit_id': dev['unit_id']
                        })
            
            # Publicar como atributos del Gateway (inventario global)
            if self.is_thingsboard:
                topic = "v1/gateway/attributes"
                # Usar nombre del Gateway desde config (ej: "RPI_EDGE")
                gateway_name = Config.EDGE_GATEWAY_NAME
                payload = {
                    gateway_name: {
                        "active_devices_count": len(active_devices),
                        "active_devices": json.dumps(active_devices),
                        "all_sensors": json.dumps(all_sensors),
                        "last_inventory_update": datetime.now().isoformat(),
                        "location": gateway_name,  # Nombre descriptivo de ubicación
                        "vendor": "Sergio Lobo",
                        "vendor_code": "0x4C6F",  # Lobo en hex
                        "alias": "Wizink Bisbal Edge",  # Alias del Gateway
                        "unit_id": 0,  # ID especial para el Gateway
                        "capabilities": "Maestro Modbus"  # Capabilities del Gateway
                    }
                }
                
                result = self.client.publish(topic, json.dumps(payload), qos=self.qos)
                
                if result.rc == mqtt.MQTT_ERR_SUCCESS:
                    logger.info(f"📊 Inventario publicado: {len(active_devices)} dispositivos, {len(all_sensors)} sensores")
                    return True
                else:
                    logger.warning(f"⚠️  Error al publicar inventario: rc={result.rc}")
                    return False
            else:
                # Publicar en topic estándar MQTT
                topic = f"{self.topic_prefix}/inventory"
                payload = {
                    "timestamp": datetime.now().isoformat(),
                    "devices": active_devices,
                    "sensors": all_sensors
                }
                
                result = self.client.publish(topic, json.dumps(payload), qos=self.qos)
                return result.rc == mqtt.MQTT_ERR_SUCCESS
        
        except Exception as e:
            logger.error(f"❌ Error al publicar inventario de sensores: {e}", exc_info=True)
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
        
        Para ThingsBoard Gateway, las alertas se publican como:
        - Telemetría con keys especiales (alert_level, alert_code, alert_message)
        - Permite visualizarlas en dashboards como eventos
        
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
            ts = timestamp or datetime.utcnow().isoformat() + 'Z'
            
            # ThingsBoard Gateway: publicar como telemetría especial
            if self.is_thingsboard and device_id:
                # Convertir device_id (unit_1) a nombre ThingsBoard (Sensor_Unit1)
                unit_num = device_id.split('_')[-1] if '_' in device_id else '1'
                device_name = f"Sensor_Unit{unit_num}"
                
                # Timestamp en milisegundos
                try:
                    from datetime import datetime as dt
                    ts_dt = dt.fromisoformat(ts.replace('Z', '+00:00'))
                    ts_ms = int(ts_dt.timestamp() * 1000)
                except:
                    ts_ms = int(datetime.now().timestamp() * 1000)
                
                # Payload ThingsBoard Gateway para alertas
                topic = "v1/gateway/telemetry"
                payload = {
                    device_name: [
                        {
                            "ts": ts_ms,
                            "values": {
                                "alert_level": level,
                                "alert_code": code,
                                "alert_message": message,
                                "alert_id": alert_id,
                                "alert_sensor": sensor_id or "N/A",
                                "alert_ack": 1 if ack else 0
                            }
                        }
                    ]
                }
                
                result = self.client.publish(topic, json.dumps(payload), qos=self.qos)
                
                if result.rc == mqtt.MQTT_ERR_SUCCESS:
                    logger.info(f"🚨 Alerta publicada a ThingsBoard: {device_name} -> {code} ({level})")
                    return True
                else:
                    logger.warning(f"⚠️  Error al publicar alerta ThingsBoard: rc={result.rc}")
                    return False
            
            # Formato MQTT estándar (fallback)
            else:
                payload = {
                    "timestamp": ts,
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
