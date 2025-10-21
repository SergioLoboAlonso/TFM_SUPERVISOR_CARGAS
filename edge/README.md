# Edge Node

Código ejecutado en la **Raspberry Pi** (o dispositivo similar) encargado de:

- Leer los datos RS-485 procedentes del módulo base.
- Validar el frame y el CRC.
- Publicar mensajes MQTT en formato JSON.
- Interactuar con la plataforma **FIWARE** (IoT Agent → Orion → QuantumLeap).

## Estructura
- `src/` → Código principal (scripts Python).
- `tests/` → Pruebas automatizadas.
- `requirements.txt` → Dependencias Python.
