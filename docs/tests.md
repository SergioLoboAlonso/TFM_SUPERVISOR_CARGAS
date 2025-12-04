# Guía de pruebas

## Firmware (PlatformIO + Unity)
- Pruebas ubicadas en `firmware/test/`.
- Se ejecutan en placa (UNO) usando el Test Runner de PlatformIO.
- Incluyen:
  - `test_crc16.cpp`: vectores estándar y caso vacío.
  - `test_modbus_map.cpp`: ventanas de lectura, escrituras válidas/ilegales, contadores de diagnóstico.
- Entrada única de Unity en `test_modbus_map.cpp` para evitar múltiples `setup()/loop()`.

## Edge (pytest)
- Pruebas previstas en `edge/tests/`.
- Casos a cubrir:
  - Delimitación por t3.5 y parsing de PDU 0x03/0x04.
  - Verificación de CRC16.
  - Mapeo Modbus→JSON (nombres estables, escalas correctas).

## Cobertura y buenas prácticas
- Para firmware, centrarse en tests de lógica pura (CRC, mapa) y pruebas de integración ligeras.
- Para Edge, añadir tests de contrato (snapshot JSON) para evitar regresiones de claves.
