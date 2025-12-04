# ModbusRTU (AVR) — Servidor RTU y Mapa de Registros

Implementación de un esclavo Modbus RTU minimalista para Arduino AVR (UNO/NANO) sobre MAX485.

## API

- `void begin(HardwareSerial& serial, uint32_t baud, uint8_t derePin)`
  - Inicializa UART a `baud`, configura DE/RE del MAX485 y calcula t1.5/t3.5.
- `void poll()`
  - Delimita por silencio ≥ t3.5, valida CRC y atiende 0x03/0x04/0x06. Llamar en cada `loop()`.

Difusión (broadcast, unit=0):
- 0x06: aplica y NO responde (norma RTU)
- 0x03/0x04: no responde

## Mapa de registros (direcciones base 0)

Escalas:
- Ángulos: centi‑grados (0.01°) → `IR_MED_ANGULO_*_CDEG`
- Temp: centi‑grados °C → `IR_MED_TEMPERATURA_CENTI`
- Aceleración: mg → `IR_MED_ACEL_*_mG`
- Giro: mdps → `IR_MED_GIRO_*_mdps`
- Peso: centi‑kg (0.01 kg) → `IR_MED_PESO_KG_CENTI` (leer y dividir entre 100 para kg)

| Banco | Dirección (hex) | Nombre | Acceso | Escala/Unid. | Descripción |
|---|---:|---|:---:|:---:|---|
| Holding | 0x0000 | HR_INFO_VENDOR_ID | R | — | Identificador proveedor (0x5446='TF') |
| Holding | 0x0001 | HR_INFO_PRODUCTO_ID | R | — | Identificador producto (0x4D30='M0') |
| Holding | 0x0002 | HR_INFO_VERSION_HW | R | — | Versión HW (major<<8 | minor) |
| Holding | 0x0003 | HR_INFO_VERSION_FW | R | — | Versión FW (major<<8 | minor) |
| Holding | 0x0004 | HR_INFO_ID_UNIDAD | R | — | Unit ID efectivo |
| Holding | 0x0005 | HR_INFO_CAPACIDADES | R | bitmask | Capacidades (RS485, MPU6050, IDENT, WIND) |
| Holding | 0x0006 | HR_INFO_UPTIME_S_LO | R | s (LSW) | Uptime segundos (parte baja) |
| Holding | 0x0007 | HR_INFO_UPTIME_S_HI | R | s (MSW) | Uptime segundos (parte alta) |
| Holding | 0x0008 | HR_INFO_ESTADO | R | bitmask | Estado dispositivo |
| Holding | 0x0009 | HR_INFO_ERRORES | R | bitmask | Últimos errores |
| Holding | 0x0010 | HR_CFG_BAUDIOS | R/W | enum | 0=9600,1=19200,2=38400,3=57600,4=115200 |
| Holding | 0x0011 | HR_CFG_MPU_FILTRO_HZ | R/W | Hz | Cutoff/filtro MPU (codificado) |
| Holding | 0x0012 | HR_CMD_GUARDAR_APLICAR | W | — | 0=noop, 0xA55A=save, 0xB007=apply |
| Holding | 0x0013 | HR_CMD_IDENT_SEGUNDOS | W | s | Iniciar Identify (0=stop) |
| Holding | 0x0014 | HR_CFG_ID_UNIDAD | R/W | — | Unit ID persistente (1..247) |
| Input   | 0x0000 | IR_MED_ANGULO_X_CDEG | R | 0.01° | Ángulo X |
| Input   | 0x0001 | IR_MED_ANGULO_Y_CDEG | R | 0.01° | Ángulo Y |
| Input   | 0x0002 | IR_MED_TEMPERATURA_CENTI | R | 0.01°C | Temperatura |
| Input   | 0x0003 | IR_MED_ACEL_X_mG | R | mg | Aceleración X |
| Input   | 0x0004 | IR_MED_ACEL_Y_mG | R | mg | Aceleración Y |
| Input   | 0x0005 | IR_MED_ACEL_Z_mG | R | mg | Aceleración Z |
| Input   | 0x0006 | IR_MED_GIRO_X_mdps | R | mdps | Velocidad angular X |
| Input   | 0x0007 | IR_MED_GIRO_Y_mdps | R | mdps | Velocidad angular Y |
| Input   | 0x0008 | IR_MED_GIRO_Z_mdps | R | mdps | Velocidad angular Z |
| Input   | 0x0009 | IR_MED_MUESTRAS_LO | R | LSW | Contador muestras (parte baja) |
| Input   | 0x000A | IR_MED_MUESTRAS_HI | R | MSW | Contador muestras (parte alta) |
| Input   | 0x000B | IR_MED_FLAGS_CALIDAD | R | bitmask | Flags de calidad |
| Input   | 0x000C | IR_MED_PESO_KG | R | 0.01 kg | Peso/carga (ej.: 12.34 kg → 1234) |
| Input   | 0x000D | IR_MED_WIND_SPEED_CMPS | R | 0.01 m/s | Velocidad del viento (m/s ×100) |
| Input   | 0x000E | IR_MED_WIND_DIR_DEG | R | grados | Dirección del viento (0–359; 0 si no hay veleta) |
| Holding | 0x0020 | HR_DIAG_TRAMAS_RX_OK | R | — | Tramas RX correctas |
| Holding | 0x0021 | HR_DIAG_RX_CRC_ERROR | R | — | Tramas RX con CRC incorrecto |
| Holding | 0x0022 | HR_DIAG_RX_EXCEPCIONES | R | — | Excepciones enviadas |
| Holding | 0x0023 | HR_DIAG_TRAMAS_TX_OK | R | — | Tramas TX enviadas |
| Holding | 0x0024 | HR_DIAG_DESBORDES_UART | R | — | Overruns UART |
| Holding | 0x0025 | HR_DIAG_ULTIMA_EXCEPCION | R | — | Último código excepción |

Límites de mapa: Holding 0x0000..0x002F, Input 0x0000..0x001F. Lecturas por trama: máx 32 palabras.

## Notas de implementación

- CRC16 Modbus (poly 0xA001, init 0xFFFF, LSB-first en palabra).
- Palabras Modbus big-endian en el cable; internamente se manejan como `uint16_t`.
- Broadcast permitido sólo en 0x06 y sin respuesta.

## Próximos pasos

- Añadir 0x10 (Write Multiple) si se necesitan escrituras de bloques (ej. alias largos).
- Exponer documentación FIWARE/MQTT si se integra en Edge.
