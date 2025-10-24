# Firmware

Código para microcontroladores AVR (Arduino UNO/NANO) que implementa un esclavo Modbus RTU sobre RS‑485 y utilidades de dispositivo (identificación LED, EEPROM, estado).

## Estructura
- `platformio.ini` (en repo raíz y en `firmware/`): configuración de entornos (UNO, NANO), flags y pines.
- `src/` → Punto de entrada (`main.cpp`). Actualmente contiene un "BlinkIdent" mínimo para validación de hardware.
- `include/` → Cabeceras globales de firmware: pines (`config_pins.h`), versión (`firmware_version.h`).
- `lib/` → Librerías locales:
	- `ModbusRTU/` → Servidor RTU y mapa de registros. Ver `lib/ModbusRTU/README.md`.
	- `BlinkIdent/` → Patrones no bloqueantes de identificación LED.
	- `EepromUtils/` → Persistencia de UnitID/alias.
	- `StateMachine/` → Orquestación (descubrimiento/claim/operar) — placeholder.
	- `utils/` → CRC16 Modbus y utilidades.
- `test/` → Pruebas Unity (PlatformIO): CRC16 y semántica del mapa de registros.

## Componentes clave

### ModbusRTU + registersModbus
- Archivo de cabecera canónica: `lib/ModbusRTU/include/registersModbus.h`.
- Reglas y contrato del mapa:
	- Direcciones base‑0. Holding 0x0000..0x002F; Input 0x0000..0x001F.
	- Lectura máx. por trama: 32 palabras (ver `MAX_*_READ`).
	- Escalas: ángulos 0.01°, temp 0.01°C, acel. mg, giro mdps.
	- Broadcast (unit=0): sólo 0x06 y sin respuesta.
- API de acceso en tiempo de ejecución: `regs_*` para leer/escribir y actualizar estado.
- Excepciones manejadas: función/valor/dirección ilegal.

Consulta el documento: `lib/ModbusRTU/README.md` (tabla completa del mapa y notas RTU).

### BlinkIdent
Patrones de parpadeo no bloqueantes para la función "Identify" (controlada por `HR_CMD_IDENT_SEGUNDOS`). Se actualiza en cada `loop()` sin `delay()`.

### EepromUtils
Persistencia de UnitID y otros metadatos. Proporciona helpers para leer/escribir de forma segura.

## Compilación y carga

- Requisitos: PlatformIO Core/VS Code + toolchain AVR.
- UNO por defecto. Para compilar y subir, usar las acciones de PlatformIO en el editor.

## Pruebas unitarias

- Ubicadas en `firmware/test/` con Unity.
- Incluyen:
	- `test_crc16.cpp`: vectores conocidos y caso vacío.
	- `test_modbus_map.cpp`: límites de ventana, escrituras válidas/ilegales, diagnósticos.
- Se ejecutan sobre la placa (HIL) usando PlatformIO Test Runner.

## Convenciones

- Nombres de registros en castellano y autoexplicativos (p.ej., `HR_INFO_VERSION_FW`).
- Mantener estabilidad de direcciones; añadir nuevos al final del banco correspondiente.
- Big‑endian en el cable; internos como `uint16_t`.

## Próximos pasos

- Reintegrar el servidor Modbus en `main.cpp` cuando se pase de Blink a integración completa.
- Añadir pruebas para 0x06 broadcast y contadores de diagnóstico bajo carga.
