# Infraestructura (Infra)

Servicios locales para pruebas e integración: broker MQTT y (próximamente) FIWARE.

## Estructura
- `docker-compose.yml` → orquesta los contenedores.
- `mosquitto/` → configuración del broker MQTT (puerto 1883, volúmenes en `mosquitto/data`).
- `fiware/` → placeholders de configuración para Orion/IoT Agent/QuantumLeap.

## Uso
1. Asegúrate de tener Docker y Docker Compose.
2. Levanta los servicios con Docker desde la raíz del repo.
3. Publica/suscribe en `mqtt://localhost:1883`.

## Puertos
- Mosquitto: 1883/TCP
- Orion/IoT Agent/QuantumLeap: se documentarán cuando se añadan.

## Notas
- Mantén los ficheros de `mosquitto.conf` sincronizados con los topics que publiques desde Edge.
- Los servicios FIWARE se añadirán de forma incremental.
