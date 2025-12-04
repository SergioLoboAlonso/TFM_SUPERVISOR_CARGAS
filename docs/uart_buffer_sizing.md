# Dimensionado del Buffer UART para Modbus RTU

## Resumen Ejecutivo

El buffer de recepción UART del Arduino se ha aumentado de 64 bytes (por defecto) a **128 bytes** para garantizar que las tramas Modbus RTU más largas puedan recibirse sin pérdida de datos, incluso cuando el bucle principal está temporalmente ocupado procesando sensores u otras tareas.

---

## 1. Contexto y Problema

### 1.1. Funcionamiento del UART en Arduino AVR

- El UART del ATmega328P recibe bytes mediante interrupciones hardware (ISR) y los almacena en un **ring buffer circular** en RAM.
- La función `Serial.available()` y `Serial.read()` consultan y extraen datos de este buffer desde el contexto del bucle principal (`loop()`).
- **Tamaño por defecto**: 64 bytes en Arduino UNO/Nano (ATmega328P).
- Si el bucle principal no llama a `poll()` con la suficiente frecuencia y el ISR sigue recibiendo bytes, el buffer puede **desbordarse** (overrun):
  - Los bytes nuevos se pierden (no se almacenan).
  - La trama queda incompleta.
  - El CRC Modbus fallará y la trama será descartada.

### 1.2. Modbus RTU y Delimitación de Trama

- **Modbus RTU** delimita tramas mediante **silencios en el bus**:
  - t3.5 caracteres (≥ 3.5 × duración de 1 carácter) marca el final de una trama.
  - t1.5 caracteres es el máximo silencio permitido **dentro** de una trama válida.
- Cada carácter transmitido en Modbus RTU (8N1) ocupa **10 bits** (1 start + 8 datos + 1 stop):
  - **Duración de 1 carácter**: `t_char = 10 bits / baudrate (bps)`

### 1.3. Escenario de Riesgo

Si el bucle principal está ocupado durante un tiempo comparable o superior al tiempo de transmisión de una trama larga, el buffer RX puede llenarse antes de que `poll()` vacíe los bytes. Esto provoca:
- Pérdida de bytes intermedios o finales.
- CRC incorrecto.
- Respuesta de excepción o falta de respuesta (dependiendo de si se puede parsear unit/func).

---

## 2. Análisis de Peor Caso

### 2.1. Trama Modbus RTU Más Larga en Este Sistema

La trama de escritura más larga soportada es **0x10 (Write Multiple Registers)** para actualizar el **alias del dispositivo** (0..64 bytes de datos ASCII empaquetados):

- **Dirección de inicio**: `HR_ID_ALIAS_LEN` (0x0030).
- **Registros a escribir**: 1 (longitud) + 32 (datos, 2 bytes ASCII por registro) = **33 registros**.
- **Estructura de la petición Modbus 0x10**:

| Campo         | Bytes | Contenido                                   |
|---------------|-------|---------------------------------------------|
| Unit ID       | 1     | ID del esclavo (1..247)                     |
| Function      | 1     | 0x10 (Write Multiple Registers)             |
| Start Address | 2     | 0x0030 (MSB, LSB)                           |
| Quantity      | 2     | 0x0021 (33 registros = 0x21 en hex)         |
| Byte Count    | 1     | 66 (33 × 2)                                 |
| Data          | 66    | 1 registro longitud + 32 registros de datos |
| CRC           | 2     | CRC16 Modbus                                |
| **TOTAL**     | **75**| **75 bytes**                                |

### 2.2. Tiempo de Transmisión de la Trama

Calculamos el tiempo en el aire para la trama más larga (75 bytes) en los baudrates configurados:

#### 2.2.1. A 115200 bps (configuración actual)

- **Duración de 1 carácter**:  
  `t_char = 10 bits / 115200 bps ≈ 0.0868 ms ≈ 86.8 μs`

- **Duración de la trama de 75 bytes**:  
  `T_trama = 75 × t_char ≈ 75 × 0.0868 ms ≈ 6.51 ms`

- **Ventana crítica** (tiempo que el loop puede estar bloqueado sin causar overrun):  
  Con buffer de 64 bytes, si el loop no vacía el buffer en **≤ 5.5 ms** (64 bytes × 86.8 μs ≈ 5.55 ms), se pierden bytes.

#### 2.2.2. A 9600 bps (peor caso de baudrate bajo)

- **Duración de 1 carácter**:  
  `t_char = 10 bits / 9600 bps ≈ 1.042 ms`

- **Duración de la trama de 75 bytes**:  
  `T_trama = 75 × 1.042 ms ≈ 78.1 ms`

- **Ventana crítica** con buffer de 64 bytes:  
  `64 × 1.042 ms ≈ 66.7 ms`

Si el loop está ocupado más de 66 ms, se pierden bytes de la trama.

---

## 3. Solución: Aumento del Buffer a 128 Bytes

### 3.1. Justificación del Tamaño

- **Trama más larga**: 75 bytes.
- **Margen de seguridad**: factor de 1.7× sobre el peor caso.
- **Buffer propuesto**: **128 bytes**.

### 3.2. Ventanas Críticas con Buffer de 128 Bytes

#### A 115200 bps

- **Ventana crítica**:  
  `128 × 0.0868 ms ≈ 11.11 ms`

- El loop puede estar ocupado hasta **11.11 ms** sin perder bytes.
- La trama más larga (75 bytes) ocupa **6.51 ms** en el aire.
- **Margen disponible**: `11.11 - 6.51 ≈ 4.6 ms` de latencia adicional del loop.

#### A 9600 bps

- **Ventana crítica**:  
  `128 × 1.042 ms ≈ 133.4 ms`

- El loop puede estar ocupado hasta **133.4 ms** sin perder bytes.
- La trama más larga (75 bytes) ocupa **78.1 ms** en el aire.
- **Margen disponible**: `133.4 - 78.1 ≈ 55.3 ms` de latencia adicional del loop.

### 3.3. Análisis de Suficiencia

En este proyecto, las operaciones típicas del bucle principal incluyen:
- Lectura del MPU6050 por I²C (< 2 ms típicamente).
- Actualización de registros Modbus (< 0.1 ms).
- Gestión de LED de identificación (no bloqueante si se usa estado).
- Llamada a `poll()` en cada iteración.

**Conclusión**: Con un buffer de 128 bytes, incluso en el peor caso de baudrate bajo (9600 bps) y una iteración de loop "lenta" (10–20 ms), el margen es suficiente para absorber la trama completa sin pérdida de datos.

---

## 4. Impacto en la RAM

### 4.1. Consumo Adicional de RAM

- **Buffer anterior**: 64 bytes.
- **Buffer nuevo**: 128 bytes.
- **Incremento**: **+64 bytes** de RAM estática.

### 4.2. Disponibilidad de RAM en ATmega328P

- **RAM total**: 2048 bytes.
- **RAM usada antes del cambio** (según última compilación): ~822 bytes (40.1%).
- **RAM usada tras el cambio**: ~886 bytes (43.3%).
- **RAM libre**: ~1162 bytes (56.7%).

### 4.3. Evaluación

El incremento de 64 bytes es **aceptable**:
- Sigue habiendo más de 1 KB libre.
- La funcionalidad crítica (Modbus + sensores) no requiere grandes buffers dinámicos adicionales.
- El margen permite futuras expansiones (más sensores, estadísticas, etc.).

---

## 5. Implementación

### 5.1. Modificación en `platformio.ini`

Se añade el flag de compilación `-DSERIAL_RX_BUFFER_SIZE=128` en ambos entornos (`uno` y `nano`):

```ini
[env:uno]
build_flags =
  -DSERIAL_RX_BUFFER_SIZE=128
  -DRS485_DERE_PIN=2
  ...

[env:nano]
build_flags =
  -DSERIAL_RX_BUFFER_SIZE=128
  -DRS485_DERE_PIN=4
  ...
```

Este flag es reconocido por el framework Arduino AVR y redefine el tamaño del ring buffer RX en `HardwareSerial.cpp`.

### 5.2. Sin Cambios en el Código de `ModbusRTU`

- La clase `ModbusRTU` no necesita modificaciones.
- Sigue usando `Serial.available()` y `Serial.read()` de forma estándar.
- El aumento del buffer es transparente para la lógica de la aplicación.

---

## 6. Verificación y Pruebas

### 6.1. Compilación

Tras aplicar el cambio, compilar el firmware con:

```bash
platformio run
```

Verificar:
- No hay errores de compilación.
- El uso de RAM reportado sigue siendo < 50% (margen seguro).

### 6.2. Pruebas en Hardware (Recomendadas)

1. **Escritura de alias largo** (64 bytes):
   - Enviar trama 0x10 con 33 registros (1 longitud + 32 datos).
   - Verificar que la escritura se acepta y el alias se actualiza correctamente.
   - Leer de vuelta el alias con 0x03 para confirmar persistencia.

2. **Simulación de loop bloqueado**:
   - Introducir un `delay(10)` en el loop principal temporalmente.
   - Enviar tramas 0x10 largas y verificar que no se generan excepciones por CRC.

3. **Test de baudrate bajo**:
   - Cambiar a 9600 bps en ambos lados.
   - Repetir las pruebas de escritura de alias.
   - Confirmar que no hay overruns incluso con loop "lento".

---

## 7. Conclusiones

- **Buffer de 128 bytes** es suficiente para absorber la trama Modbus RTU más larga (75 bytes) con margen de seguridad >1.7×.
- **Impacto en RAM**: +64 bytes, aceptable dado que queda >50% de RAM libre.
- **Ventanas críticas**:
  - A 115200 bps: el loop puede estar ocupado hasta **11.1 ms** sin pérdida de datos.
  - A 9600 bps: el loop puede estar ocupado hasta **133.4 ms** sin pérdida de datos.
- **Recomendación**: Mantener el bucle principal no bloqueante (sin `delay()` largos) y llamar a `poll()` en cada iteración para máxima robustez.

---

## 8. Referencias

- **Modbus Application Protocol Specification V1.1b3**: [Modbus.org](https://modbus.org/docs/Modbus_Application_Protocol_V1_1b3.pdf)
- **Modbus over Serial Line Specification and Implementation Guide V1.02**: [Modbus.org](https://modbus.org/docs/Modbus_over_serial_line_V1_02.pdf)
- **ATmega328P Datasheet**: Atmel/Microchip, USART section.
- **Arduino HardwareSerial**: Framework Arduino AVR, `HardwareSerial.h` y `HardwareSerial.cpp`.

---

## Historial de Cambios

| Fecha       | Versión | Cambio                                              |
|-------------|---------|-----------------------------------------------------|
| 2025-11-01  | 1.0     | Creación inicial del documento de dimensionado.    |
