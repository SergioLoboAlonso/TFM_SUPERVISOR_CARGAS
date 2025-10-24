# Edge Node

Lógica de borde en Python (Raspberry Pi) para leer RS‑485/Modbus RTU, traducir el mapa de registros a JSON estable y publicar en MQTT, integrándose con FIWARE.

## Estructura
- `src/main.py` → Entrypoint (abrir puerto serie, bucle de lectura, publicación MQTT).
- `src/reader/` → Utilidades de parsing RTU (delimitación t3.5, CRC16, decodificación de PDU).
- `tests/` → Pruebas con PyTest (unitarias del parser y de mapeo JSON).
- `requirements.txt` → Dependencias (pyserial, paho-mqtt, pytest, black).

## Flujo esperado
1. Abrir el puerto serie RS‑485 (parametrizable) y configurar velocidad según `HR_CFG_BAUDIOS`.
2. Leer bytes, delimitar por silencio ≥ t3.5.
3. Verificar CRC16 (poly 0xA001, init 0xFFFF) y función (0x03/0x04).
4. Mapear direcciones Modbus a claves JSON estables (snake_case) p.ej.:
	- `ir.angulo_x_cdeg`, `ir.temperatura_centi`, `hr.info.version_fw`, `hr.diag.tramas_rx_ok`.
5. Publicar en MQTT (Mosquitto local) con timestamp monotónico del Edge.
6. (Opcional) Rellenar payload para IoT Agent FIWARE.

## MQTT
- Broker local: Mosquitto en `infra/`.
- Tema sugerido: `tfm/supervisor/<unit_id>/telemetry`.
- Formato: JSON, claves estables y escalas documentadas (0.01°C, mg, mdps).

## FIWARE (futuro próximo)
- IoT Agent (Ultralight/JSON) para transformar la telemetría al NGSI.
- Orion como Context Broker, y QuantumLeap para históricos.
- El wiring se añadirá en `infra/fiware/` y aquí se documentarán topics/atributos.

## Desarrollo
- Formato: `black`.
- Pruebas: `pytest` en `edge/tests/`.
- Evitar asumir respuestas a broadcast RTU; el firmware no responde a unit=0.
