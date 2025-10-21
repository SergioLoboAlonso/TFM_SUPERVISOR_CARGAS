# Firmware

Código para los microcontroladores (Arduino) que actúan como:
- **Sensor remoto:** mide inclinación mediante IMU y envía datos por RS-485.
- **Módulo base:** recibe los datos del sensor y los retransmite al nodo Edge.

## Estructura
- `src/` → Código principal (.ino o PlatformIO).
- `include/` → Cabeceras y configuraciones comunes.
- `lib/` → Librerías locales (filtros, CRC, comunicación, etc.).
- `test/` → Pruebas unitarias o de integración en entorno embebido.
