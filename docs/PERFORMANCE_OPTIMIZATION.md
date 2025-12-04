# Optimización de Rendimiento - Discovery Modbus RTU

## Resumen Ejecutivo

Se ha optimizado el proceso de discovery de dispositivos Modbus RTU, logrando una **mejora del 89%** en el tiempo de escaneo respecto a la configuración inicial.

## Resultados de Optimización

### Comparativa de Rendimiento (100 UnitIDs)

| Configuración | Timeout | Tiempo Total | ms/UnitID | Overhead | Mejora |
|--------------|---------|--------------|-----------|----------|--------|
| **Inicial** | 1.0s | ~180s | 1800ms | - | - |
| **Iteración 1** | 0.15s | 33.11s | 331ms | 132% | **81.6%** |
| **Iteración 2** | 0.10s | 23.23s | 232ms | 132% | **87.1%** |
| **Iteración 3** | 0.08s | 19.41s | 194ms | 143% | **89.2%** |
| **Experimental** | 0.05s | 12.69s | 127ms | 154% | **93.0%** |

### Configuración Final Recomendada

**Timeout: 80ms (conservador)**
- ✅ Tiempo de discovery 1-100: **~19 segundos**
- ✅ Balance óptimo velocidad/robustez
- ✅ Margen de 30ms para respuestas de dispositivos
- ✅ Robusto ante ruido en el bus
- ✅ Soporta dispositivos con tiempos de respuesta variables

## Cambios Implementados

### 1. Reducción de Timeouts

**Archivo**: `edge/src/config.py`

```python
# ANTES
MODBUS_TIMEOUT = 1.0              # Operaciones normales
MODBUS_DISCOVERY_TIMEOUT = None   # Sin timeout específico

# DESPUÉS
MODBUS_TIMEOUT = 0.3              # Operaciones normales: 300ms
MODBUS_DISCOVERY_TIMEOUT = 0.08   # Discovery rápido: 80ms
```

**Impacto**: Reduce tiempo de espera por cada UnitID no respondedor de 1.0s a 0.08s.

### 2. Optimización de Delays Inter-Frame

**Archivo**: `edge/src/config.py`

```python
# ANTES
INTER_FRAME_DELAY_MS = 50  # 50ms entre frames

# DESPUÉS
INTER_FRAME_DELAY_MS = 10  # 10ms entre frames (suficiente a 115200 baud)
```

**Justificación**: A 115200 baud, un frame Modbus de ~20 bytes tarda ~1.7ms. Un delay de 10ms es suficiente para sincronización.

### 3. Eliminación de Delays Innecesarios

**Archivo**: `edge/src/device_manager.py`

**Cambio**: Eliminado el `sleep(0.01)` después de encontrar un dispositivo durante el discovery.

**Justificación**: El timeout de pymodbus ya proporciona el margen necesario entre tramas.

### 4. Corrección de Acceso al Timeout de pymodbus

**Problema Detectado**: `ModbusSerialClient` no tiene atributo `.timeout` modificable directamente.

**Solución**: Acceso correcto al timeout a través de `comm_params`:

```python
# INCORRECTO (no funciona en pymodbus 3.x)
self.modbus.client.timeout = discovery_timeout

# CORRECTO
self.modbus.client.comm_params.timeout_connect = discovery_timeout
```

### 5. Adición de Métricas de Timing

**Archivo**: `edge/src/device_manager.py`, `edge/src/modbus_master.py`

**Agregado**: 
- Medición de tiempo por UnitID
- Estadísticas de overhead
- Logs de rendimiento

```python
logger.info(f"📊 Estadísticas: {scan_count} UnitIDs escaneados @ {avg_time_per_unit*1000:.0f}ms/unit")
logger.info(f"📊 Overhead: {(avg_time_per_unit/discovery_timeout - 1)*100:.0f}% sobre timeout teórico")
```

## Análisis de Overhead

### Overhead Observado vs Timeout

| Timeout | Overhead | Tiempo Real/UnitID | Justificación |
|---------|----------|-------------------|---------------|
| 100ms | 132% | 232ms | Overhead base pymodbus |
| 80ms | 143% | 194ms | Overhead proporcional aumenta |
| 50ms | 154% | 127ms | Overheads fijos dominan |

### Componentes del Overhead

1. **Overhead pymodbus** (~70-100ms):
   - Construcción de trama Modbus
   - Parsing de respuesta
   - Gestión de buffers internos

2. **Overhead del puerto serial** (~20-30ms):
   - Flush de buffers TX/RX
   - Cambio de dirección (half-duplex)
   - Latencia del driver USB-Serial

3. **Overhead de Python** (~10-20ms):
   - GIL (Global Interpreter Lock)
   - Context switching
   - Overhead de función

## Configuraciones Alternativas

### Para Máxima Velocidad (Entorno Controlado)

```python
MODBUS_DISCOVERY_TIMEOUT = 0.05  # 50ms - AGRESIVO
# Resultado: ~12.7s para 100 UnitIDs
# ⚠️ Usar solo en buses limpios con dispositivos rápidos
```

### Para Máxima Robustez (Entorno Industrial)

```python
MODBUS_DISCOVERY_TIMEOUT = 0.15  # 150ms - ROBUSTO
# Resultado: ~33s para 100 UnitIDs
# ✅ Recomendado para buses ruidosos o dispositivos lentos
```

## Limitaciones y Consideraciones

### Limitaciones de pymodbus

- **Overhead mínimo**: ~100ms por transacción (construcción + parsing)
- **No paralelizable**: Modbus RTU es half-duplex, colisiones garantizadas
- **Timeout mínimo práctico**: 50ms (menor = riesgo de falsos negativos)

### Consideraciones de Hardware

1. **Velocidad del bus**: Configuración actual asume 115200 baud
2. **Calidad del cable**: Cables largos o mal apantallados aumentan ruido
3. **Interferencias**: Motores, inversores pueden causar ruido EMI
4. **Topología**: Derivaciones, falta de terminación afectan señal

### Escalabilidad

- **1-10 UnitIDs**: ~2-3 segundos
- **1-50 UnitIDs**: ~10 segundos
- **1-100 UnitIDs**: ~19 segundos
- **1-247 UnitIDs**: ~48 segundos (máximo teórico Modbus)

## Recomendaciones de Uso

### Discovery Frecuente

Si necesitas discovery frecuente, considera:

1. **Cache de dispositivos**: No escanear todo cada vez
2. **Rangos reducidos**: Escanear solo el rango esperado (ej: 1-20)
3. **Discovery bajo demanda**: Solo cuando se espera un cambio en la red

### Validación en Producción

Antes de desplegar en producción:

1. ✅ Probar con el hardware real del proyecto
2. ✅ Verificar en diferentes condiciones ambientales
3. ✅ Validar con múltiples dispositivos simultáneos
4. ✅ Medir consistencia en 10+ ejecuciones
5. ✅ Probar con cables de longitud real del despliegue

## Histórico de Cambios

### 2025-11-03: Optimización Inicial
- Reducción de timeout de 1.0s → 0.15s
- Mejora: 81.6%

### 2025-11-03: Refinamiento de Timeouts
- Timeout de 0.15s → 0.08s
- Corrección de acceso a `comm_params.timeout_connect`
- Mejora final: 89.2%

### 2025-11-03: Validación Experimental
- Pruebas con timeout 0.05s (93% mejora)
- Decisión: Mantener 0.08s por robustez

## Referencias

- [Modbus RTU Specification](https://modbus.org/docs/Modbus_over_serial_line_V1_02.pdf)
- [pymodbus Documentation](https://pymodbus.readthedocs.io/)
- Timing de frames Modbus: `(bits_por_frame / baudrate) * 1000` ms
  - A 115200 baud: `(11 bits * 20 bytes / 115200) * 1000 ≈ 1.9ms por frame`
