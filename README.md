# TFM_SUPERVISOR_CARGAS
ESTE PROYECTO UTILIZA COMUNICACIÓN RS485 MODBUS DESDE UN ARDUINO HACIA UNA PLATAFORMA EDGE BASADA EN RASPBERRY PI QUE PROCESA LOS DATOS Y LOS TRANSMITE POR MQTT A UNA PLATAFORMA CLOUD.

Estructura general
- `firmware/` → Código Arduino (sensor remoto y módulo base).
- `edge/` → Nodo Edge (Raspberry Pi): lectura RS-485, MQTT y envío a FIWARE.
- `infra/` → Infraestructura local (Docker, MQTT, Orion, etc.).
- `docs/` → Documentación técnica y memoria del TFM.
- `tests/` → Plan de pruebas y resultados.
- `.vscode/` → Configuración del entorno de trabajo en VS Code.