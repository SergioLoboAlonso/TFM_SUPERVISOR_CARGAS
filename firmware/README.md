# Firmware

Esclavo Modbus RTU para AVR (Arduino UNO/NANO) con soporte multi-sensor modular.

## Configuración

Editar `platformio.ini`:

```ini
build_flags =
  -DSENSORS_MPU_ENABLED=1
  -DSENSORS_TEMP_ENABLED=0
  -DSENSORS_LOAD_ENABLED=0
  -DSENSORS_WIND_ENABLED=0
```

## Compilación

```bash
pio run -e uno -t upload
```

## Sensores Soportados

- MPU6050 (accel/gyro/temp)
- Load Cell
- Temperature
- Wind

## Comunicación

- Protocolo: Modbus RTU
- Baudrate: 115200 bps
- Interfaz: RS-485 half-duplex

## Registros Modbus

| Dirección | Tipo | Descripción |
|-----------|------|-------------|
| 0x0000    | R    | Firmware version |
| 0x0001    | R/W  | Unit ID |
| 0x0010    | R/W  | Identify LED |
| 0x0100+   | R    | Telemetría |

## Persistencia

EEPROM: Unit ID (0x00), Alias (0x01+)
