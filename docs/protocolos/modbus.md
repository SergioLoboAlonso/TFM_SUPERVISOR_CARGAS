# Protocolo Modbus RTU

Esta capa define el contrato de comunicación entre el maestro (Edge) y el esclavo (Firmware) mediante RS‑485.

## Enlace físico
- RS‑485 half‑duplex con MAX485 (pin DE/RE gestionado por firmware).
- UART 8N1.

## Temporización
- Delimitación por silencio del bus:
  - t1.5 ≈ 1.5 caracteres (usado internamente como margen)
  - t3.5 ≈ 3.5 caracteres → marca fin de trama
- Para 8N1, 1 carácter ≈ 10 bits → `char_us ≈ 10e6/baud`.

## CRC16 Modbus
- Polinomio: 0xA001
- Inicial: 0xFFFF
- Byte order en la palabra CRC: LSB primero

## Funciones soportadas
- 0x03 Read Holding Registers
- 0x04 Read Input Registers
- 0x06 Write Single Register

## Broadcast
- Unit ID 0 → broadcast.
- Sólo se aplica en 0x06 y no se responde (norma RTU).

## Endianness
- Cada registro (16 bits) se transmite big‑endian (MSB→LSB). Internamente el firmware trata valores como `uint16_t`.

## Mapa de registros
- Las direcciones son base‑0.
- Holding: 0x0000..0x002F. Input: 0x0000..0x001F.
- Lecturas por trama limitadas a 32 palabras.

Consulta la tabla completa y nombres canónicos en `firmware/lib/ModbusRTU/README.md`.

## Errores y excepciones
- Se emiten códigos estándar:
  - 0x01 Función ilegal
  - 0x02 Dirección ilegal
  - 0x03 Valor ilegal
- Los contadores de diagnóstico se exponen en Holding (tramas RX/TX, CRC erróneo, etc.).
