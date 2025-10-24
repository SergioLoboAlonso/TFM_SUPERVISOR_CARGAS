# ModbusRTU (AVR) — Esqueleto servidor RTU

Este módulo implementa un servidor Modbus RTU mínimo para Arduino AVR (UNO/NANO) sobre MAX485.

## API

- `void begin(HardwareSerial& serial, uint32_t baud, uint8_t derePin)`
  - Inicializa UART a `baud` y configura el pin DE/RE del MAX485 (HIGH=TX, LOW=RX).
- `void poll()`
  - Lee bytes entrantes, valida CRC y sirve 0x03/0x04/0x06. Llamar con alta frecuencia desde `loop()`.

## Funciones soportadas (MVP)

- 0x03 Read Holding Registers
- 0x04 Read Input Registers (mismo mapeo por simplicidad)
- 0x06 Write Single Register (registros de identify y provision de UnitID)

Difusión (broadcast, unit=0):
- 0x06: aplica la acción y NO responde.
- 0x03/0x04: no responde.

## Mapa de registros (resumen)

- DATA: `REG_ANGLE_X`, `REG_ANGLE_Y`, `REG_STATUS`, `REG_VIN_mV`
- IDENTITY: vendor/model (ASCII 16B), `REG_ID_HW_REV`, `REG_ID_FW_REV`, serial, alias (len+datos)
- DISCOVERY/CLAIM/IDENT: `REG_DISCOVERY_STATE`, `REG_UNITID_ACTIVE`, `REG_UNITID_STORED`, `REG_CLAIM_STATUS`, `REG_IDENT_*`
- PROVISION: `REG_PROV_UNITID` (escritura 0x06, persiste en EEPROM)

Ver `firmware/include/registers.h` para el contrato completo.

## Flujo interno

1. `poll()` acumula 8 bytes (PDU mínima de 0x03/0x04/0x06) y valida CRC16 (poly 0xA001, init 0xFFFF).
2. `handleRequest()` decide por función: 0x03/0x04 → `handleReadHolding`, 0x06 → `handleWriteSingle`.
3. `readSingleRegister()` y `writeSingleRegister()` mapean direcciones a variables del espacio `Registers`.
4. `sendResponse()` conmuta DE/RE, envía PDU + CRC y vuelve a RX.

## Integración con `main`

- Llamar a `Registers::initStatic()` antes de `begin()` para cargar UnitID/alias desde EEPROM.
- En el `loop()`, llamar a `Registers::updateMockMeasurements()` (hasta integrar sensores) y a `s_modbus.poll()`.
- Sincronizar `BlinkIdent` leyendo `Registers::g_identState` y `g_identTimeoutS`.

## Próximos pasos sugeridos

- Soporte 0x10 (Write Multiple Registers) para escritura de alias por bloques.
- Tabla de registros con callbacks por rango en lugar de `if` encadenados.
- Timeouts de trama (inter-char/inter-frame) si se amplían funciones.
