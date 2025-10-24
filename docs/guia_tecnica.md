# Guía técnica del proyecto

Esta guía resume cómo está construido el proyecto y cómo entender el código leyendo sus módulos y documentación.

## Visión general
- Capa Firmware (AVR/Arduino): esclavo Modbus RTU sobre RS‑485, mapa de registros, utilidades de dispositivo.
- Capa Edge (Python/RPi): lectura Modbus RTU por serie, validación, mapeo a JSON y publicación MQTT, integración FIWARE.
- Capa Infra (Docker): broker Mosquitto y, próximamente, servicios FIWARE (IoT Agent, Orion, QuantumLeap).

## Flujos principales
1. Firmware mide/gestiona estado y expone registros Modbus (Input/Holding).
2. Edge lee frames RTU, verifica CRC, consulta registros y publica JSON en MQTT.
3. Infra provee broker para pruebas y, después, el stack FIWARE para contexto e históricos.

## Repositorio y carpetas
- `firmware/` → código embebido y librerías locales.
- `edge/` → scripts Python del nodo de borde.
- `infra/` → docker-compose y configuración de servicios.
- `docs/` → documentación general (esta guía, protocolos, normas, pruebas).

## Cómo construir y probar
- Firmware: usar PlatformIO en VS Code.
  - Compila: entorno UNO por defecto.
  - Pruebas Unity en `firmware/test/` (se ejecutan en placa).
- Edge: instalar `requirements.txt`, ejecutar `pytest`, y lanzar `src/main.py`.
- Infra: levantar con Docker Compose para disponer de Mosquitto (1883).

## Contrato Modbus RTU
- Ver `firmware/lib/ModbusRTU/README.md` y `docs/protocolos/modbus.md`.
- Reglas clave: direcciones base‑0, palabras big‑endian en el cable, CRC16 (0xA001), broadcast sólo en 0x06 sin respuesta.

## Nombres y convenciones
- Registros con nombres en castellano (`HR_INFO_*`, `IR_MED_*`, `HR_DIAG_*`).
- Estabilidad de direcciones: no renumerar; añadir al final del banco.
- MQTT: claves JSON en snake_case; incluir timestamp desde Edge.

## Módulos principales
- `ModbusRTU` (firmware): parser/servidor 0x03/0x04/0x06; integra con `registersModbus`.
- `registersModbus` (firmware): estado y API `regs_*` para lecturas/escrituras.
- `BlinkIdent` (firmware): identificación visual controlada por un registro comando.
- `Edge reader` (python): delimita t3.5, calcula CRC, traduce a JSON.

## Guías específicas
- Firmware: ver `firmware/README.md`.
- Edge: ver `edge/README.md`.
- Infra: ver `infra/README.md`.

## Próximos pasos
- Reintegrar Modbus en `main.cpp`.
- Añadir documentación FIWARE detallada (atributos NGSI, mapeos IoT Agent).
- Pruebas de carga de diagnóstico (contadores RX/TX, CRC, excepciones).
