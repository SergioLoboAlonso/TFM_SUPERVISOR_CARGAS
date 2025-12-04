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

### Medidas actuales (Input Registers 0x0000 base-0)

- 0x0000 `IR_MED_ANGULO_X_CDEG` — Ángulo X (0.01°)
- 0x0001 `IR_MED_ANGULO_Y_CDEG` — Ángulo Y (0.01°)
- 0x0002 `IR_MED_TEMPERATURA_CENTI` — Temperatura (0.01°C)
- 0x0003..0x0005 `IR_MED_ACEL_*_mG` — Aceleración X/Y/Z (mg)
- 0x0006..0x0008 `IR_MED_GIRO_*_mdps` — Velocidad angular X/Y/Z (mdps)
- 0x0009..0x000A `IR_MED_MUESTRAS_LO/HI` — Contador de muestras (LSW/MSW)
- 0x000B `IR_MED_FLAGS_CALIDAD` — Flags de calidad (bitmask)
- 0x000C `IR_MED_PESO_KG_CENTI` — Peso/carga en centi‑kg (0.01 kg). Para obtener kg dividir entre 100.

### Extensiones de viento y estadísticas (Input Registers)

- 0x000D `IR_WIND_SPEED_CMPS_X100` — Velocidad del viento (cm/s ×100). Conversión: m/s = reg/100, km/h = reg×0.036
- 0x000E `IR_WIND_DIRECTION_DEG` — Dirección del viento (0..359°)

Estadísticas de ventana (tumbling) de 5s, emitidas cuando la ventana se completa en firmware:

- 0x000F `IR_STAT_WIND_MIN_CMPS_X100` — Viento mínimo (cm/s ×100)
- 0x0010 `IR_STAT_WIND_MAX_CMPS_X100` — Viento máximo (cm/s ×100)
- 0x0011 `IR_STAT_WIND_AVG_CMPS_X100` — Viento medio (cm/s ×100)
- 0x0012..0x0014 `IR_STAT_ACC_X_{MIN,MAX,AVG}_mG`
- 0x0015..0x0017 `IR_STAT_ACC_Y_{MIN,MAX,AVG}_mG`
- 0x0018..0x001A `IR_STAT_ACC_Z_{MIN,MAX,AVG}_mG`

Nota: el Edge puede leer de una sola vez 27 registros desde 0x0000 para obtener base + viento + estadísticas. En dispositivos sólo‑viento se recomienda la ventana 0x0009..0x0011 (9 registros) para obtener contador, flags, carga, viento actual y estadísticas de viento.

### Configuración de intervalo de muestreo (Holding Registers)

- 0x0015 `HR_CFG_POLL_INTERVAL_MS` — Intervalo global de muestreo en el firmware (ms). Rango recomendado: 10..5000.

Consideraciones:
- El intervalo del firmware controla la frecuencia de adquisición y cálculo de estadísticas en el dispositivo.
- El Edge tiene su propio intervalo de polling y un refresco por dispositivo; ambos afectan la carga del bus pero no el cálculo interno de ventanas del dispositivo.

## Errores y excepciones
- Se emiten códigos estándar:
  - 0x01 Función ilegal
  - 0x02 Dirección ilegal
  - 0x03 Valor ilegal
- Los contadores de diagnóstico se exponen en Holding (tramas RX/TX, CRC erróneo, etc.).
