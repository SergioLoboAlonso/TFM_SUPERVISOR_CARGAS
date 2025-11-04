# Identify: Función Propietaria 0x41

## ✅ Implementación Correcta

El comando **Identify NO se hace escribiendo en registros**, sino mediante la **función propietaria 0x41**.

### Cómo Funciona (Firmware)

Cuando el maestro envía la trama: `[UnitID, 0x41, CRC_L, CRC_H]`

El firmware (en `ModbusRTU.cpp`):
1. Recibe la función 0x41
2. Llama a `handleIdentifyBlinkAndInfo(unit)`
3. Esta función internamente escribe `IDENTIFY_DEFAULT_SECS` (5s) en `HR_CMD_IDENT_SEGUNDOS`
4. Retorna información ASCII del dispositivo (vendor, product, firmware, hardware, etc.)
5. El LED parpadea durante 5 segundos

### Código Firmware (ya implementado)

```cpp
// ModbusRTU.cpp línea 235-242
case 0x41: { // Proprietary Identify + Info
  if(n < 4){ sendException(unit, func, MB_EX_ILLEGAL_DATA_VALUE); return; }
  if(isBroadcast) return;
  handleIdentifyBlinkAndInfo(unit);
  break;
}

// ModbusRTU.cpp línea 311-313
void ModbusRTU::handleIdentifyBlinkAndInfo(uint8_t unit){
  // Disparar Identify por defecto
  regs_write_holding(HR_CMD_IDENT_SEGUNDOS, IDENTIFY_DEFAULT_SECS);
  // ... construye y envía respuesta con info del dispositivo
}
```

### Código Maestro (Edge)

El maestro Python implementa `send_identify_0x41()` en `modbus_client.py`:
- Construye trama raw: `[UnitID, 0x41, CRC16]`
- Envía por puerto serial
- Parsea respuesta con información ASCII
- El LED parpadea automáticamente por ~5 segundos

## ⚠️ Nota Importante

**NO es necesario descomentar `apply_ident_from_register()`** en `main.cpp`.

Esa función era para el caso alternativo de escribir directamente en el registro `HR_CMD_IDENT_SEGUNDOS` (0x0013), pero **no se usa** porque preferimos la función 0x41 que además retorna información del dispositivo.

## 🧪 Prueba

1. Reinicia el servidor Edge:
   ```bash
   cd edge
   pkill -9 -f 'python3 src/app.py'
   ./start_edge.sh
   ```

2. Abre `/config` en el navegador
3. Haz discovery del dispositivo
4. Presiona el botón 🔦 (Identify)
5. El LED del Arduino debe parpadear por ~5 segundos
6. El log mostrará: "✅ Identify 0x41 activado en unit X" + información ASCII

## 🔍 Verificación en Log

Busca estas líneas en el log del servidor:

```
Identificando dispositivo 2 con función 0x41 (LED ~5s)
Enviando 0x41 a unit 2: 02410000
Respuesta 0x41: 024128025fff54... (XX bytes)
✅ Identify 0x41 activado en unit 2
   Info: TFM0 v0.1 HW1.0 ...
```
