# Convenciones de código y proyecto

## Registros Modbus
- Nombres en castellano y autoexplicativos (HR_INFO_*, HR_CFG_*, HR_CMD_*, IR_MED_*, HR_DIAG_*).
- Direcciones base‑0, no renumerar; añadir nuevos al final del banco correspondiente.
- Documentar cualquier adición significativa en el README del módulo Modbus.

## Endianness y escalas
- Big‑endian en el cable (MSB→LSB). Internamente `uint16_t`.
- Escalas fijas (0.01°C, 0.01°, mg, mdps). Evitar `float` en MCU.

## Broadcast y tiempos
- Aceptar broadcast en firmware, no responder a unit=0.
- Respetar t1.5/t3.5 para delimitar RTU.

## Mensajería MQTT
- Claves JSON en snake_case y estables a lo largo del tiempo.
- Incluir timestamp del Edge.

## Estilo y tooling
- Firmware: PlatformIO + Unity tests.
- Edge: black (formato), pytest (pruebas), flake8 opcional.

## Commits y versionado
- Mensajes concisos: prefijo de área (Firmware/Edge/Infra/Docs) + resumen.
- Bump de versión en `firmware/include/firmware_version.h` cuando cambie el contrato.
