# Edge Command Line - CLI para Supervisor de Cargas

Versión de línea de comandos del Edge Layer, sin dependencias web.

## 📋 Características

- ✅ **Discovery automático** de dispositivos Modbus RTU
- ✅ **Lectura de telemetría** (ángulos, temperatura, aceleración, viento)
- ✅ **Polling continuo** con intervalo configurable
- ✅ **Identify** (parpadeo LED) para ubicar dispositivos
- ✅ **Gestión de alias** (lectura/escritura EEPROM)
- ✅ **Cambio de UnitID** persistente
- ✅ **Logs claros** con colores en terminal
- ✅ **Sin servidor web** - ejecutable autónomo

## 🚀 Instalación

```bash
# Ya comparte las dependencias con edge/
cd ~/Desktop/TFM_SUPERVISOR_CARGAS/edge_command_line

# Las dependencias se toman del edge principal
# No requiere instalación adicional
```

## 🎯 Uso

### Modo Interactivo (Recomendado)

```bash
python3 edge_cli.py
```

Muestra un menú con todas las opciones:
```
1 - Discovery de dispositivos
2 - Listar dispositivos en caché
3 - Leer telemetría (una vez)
4 - Polling continuo
5 - Identify (parpadeo LED)
6 - Cambiar alias
7 - Cambiar UnitID
8 - Mostrar este menú
0 - Salir
```

### Modo Comando (Scripts/Automatización)

#### Discovery rápido

```bash
# Discovery de UnitID 1-10 (default)
python3 edge_cli.py --discover

# Discovery personalizado 1-20
python3 edge_cli.py --discover 1 20
```

#### Polling continuo

```bash
# Polling del UnitID 2 cada 2s (default)
python3 edge_cli.py --poll 2

# Polling del UnitID 16 cada 5s
python3 edge_cli.py --poll 16 --interval 5
```

#### Identify device

```bash
# Identify UnitID 2 por 10s (default)
python3 edge_cli.py --identify 2

# Identify UnitID 2 por 30s
python3 edge_cli.py --identify 2 --duration 30
```

#### Listar dispositivos

```bash
# Lista todos los dispositivos en caché
python3 edge_cli.py --list
```

## 📊 Ejemplo de Salida

### Discovery

```
======================================================================
            DISCOVERY: UnitID 1..10
======================================================================

ℹ Leyendo 10 registros desde 0x0000...
✓ Encontrados 1 dispositivo(s) en 2.58s

UnitID 16
  Vendor:  LoboEdge (ID: 0x4C6F)
  Product: Wind Sensor (ID: 0x5730)
  HW:      1.0
  FW:      1.2
  Alias:   Sensor-Viento-Terraza
  Caps:    Viento
  Estado:  online
  Visto:   2025-11-24 23:50:15
```

### Telemetría

```
======================================================================
            LECTURA TELEMETRÍA - UnitID 16
======================================================================

ℹ Leyendo 9 registros desde 0x0009...
✓ Telemetría leída correctamente

Telemetría - UnitID 16 (Sensor-Viento-Terraza)
Timestamp: 2025-11-24T23:50:20.123456

  Viento:
    Velocidad:  12.50 m/s ( 45.00 km/h)
    Dirección: 270°

  Estadísticas Viento (5s):
    Mín:  11.20 m/s
    Máx:  14.80 m/s
    Med:  12.95 m/s

  Muestras: 45678
```

## 🔧 Configuración

La CLI usa el mismo archivo `.env` que el edge web:

```bash
# Copiar ejemplo si no existe
cp ../edge/.env.example ../edge/.env

# Editar configuración
nano ../edge/.env
```

Variables principales:
```bash
MODBUS_PORT=/dev/ttyACM0      # Puerto RS-485
MODBUS_BAUDRATE=115200        # Velocidad
MODBUS_TIMEOUT=1.0            # Timeout en segundos
```

## 🎨 Características de Presentación

### Colores ANSI

- 🟢 **Verde** - Éxitos y confirmaciones
- 🔴 **Rojo** - Errores
- 🟡 **Amarillo** - Advertencias
- 🔵 **Cyan** - Información
- **Negrita** - Encabezados y destacados

### Logs Estructurados

Todos los logs se escriben también en `edge.log` para debugging:

```bash
# Ver logs en tiempo real
tail -f ../edge/edge.log
```

## 🔌 Dependencias Compartidas

La CLI reutiliza los módulos del edge web:

```python
from modbus_master import ModbusMaster      # Cliente Modbus RTU
from device_manager import DeviceManager    # Gestión de dispositivos
from data_normalizer import DataNormalizer  # Normalización telemetría
from config import Config                   # Configuración (.env)
from logger import logger                   # Logging estructurado
```

**Ventaja**: Sin duplicación de código, mantiene compatibilidad.

## 📝 Casos de Uso

### 1. Testing Rápido de Dispositivo

```bash
# Discovery + lectura simple
python3 edge_cli.py --discover
python3 edge_cli.py --poll 16 --interval 1
```

### 2. Configuración Inicial

```bash
python3 edge_cli.py
# Opción 1: Discovery
# Opción 6: Cambiar alias → "Sensor-Planta-1"
# Opción 7: Cambiar UnitID → 2
```

### 3. Monitoreo en Producción

```bash
# Polling continuo con logs
python3 edge_cli.py --poll 2 --interval 10 >> sensor_2.log 2>&1 &
```

### 4. Scripts de Automatización

```bash
#!/bin/bash
# auto_discovery.sh

echo "Buscando dispositivos..."
python3 edge_cli.py --discover 1 20

echo "Identificando dispositivo 2..."
python3 edge_cli.py --identify 2 --duration 5

echo "Leyendo telemetría..."
python3 edge_cli.py --poll 2 --interval 1
```

## 🐛 Debugging

### Modo verbose

```bash
# Editar .env y cambiar
LOG_LEVEL=DEBUG

# Ejecutar CLI
python3 edge_cli.py --poll 2
```

### Revisar logs

```bash
# Logs generales
cat ../edge/edge.log

# Solo errores
grep ERROR ../edge/edge.log

# Últimos 50 eventos
tail -50 ../edge/edge.log
```

### Test de conexión Modbus

```bash
# Verificar puerto RS-485
ls -la /dev/ttyACM* /dev/ttyUSB*

# Permisos (si necesario)
sudo usermod -a -G dialout $USER
```

## 🆚 CLI vs Web UI

| Característica | CLI | Web UI |
|----------------|-----|--------|
| Instalación | Ninguna (ya incluido) | Servidor Flask |
| Dependencias | Solo Python básico | Flask, Socket.IO, etc. |
| Uso remoto | SSH | Navegador web |
| Automatización | Scripts bash | API REST |
| Telemetría en vivo | Polling manual | WebSocket automático |
| Multi-usuario | No | Sí |
| Curva aprendizaje | Baja | Media |

**Cuándo usar CLI**:
- ✅ Testing rápido
- ✅ Configuración inicial
- ✅ Debugging
- ✅ Scripts automatizados
- ✅ Entorno sin GUI

**Cuándo usar Web UI**:
- ✅ Monitoreo multi-dispositivo
- ✅ Dashboard visual
- ✅ Acceso remoto fácil
- ✅ Múltiples usuarios
- ✅ Gráficos en tiempo real

## 🔐 Seguridad

- ⚠️ **Sin autenticación** - Solo para red local confiable
- ⚠️ **Sin cifrado** - Modbus RTU sin encriptación
- ✅ **Sin red** - Solo local, no expone puertos
- ✅ **Logs auditables** - Todas las operaciones registradas

## 📚 Ayuda Integrada

```bash
# Ver ayuda completa
python3 edge_cli.py --help

# Ver ejemplos
python3 edge_cli.py --help | grep -A 10 "Ejemplos:"
```

## 🎓 Para Defensa del TFM

**Ventajas arquitectónicas**:

1. **Separación de responsabilidades**
   - CLI = interfaz usuario
   - Core modules = lógica reutilizable

2. **Código limpio y documentado**
   - Comentarios claros
   - Nombres descriptivos
   - Estructura simple

3. **Versatilidad**
   - Mismo backend, múltiples frontends
   - CLI + Web UI comparten código

4. **Facilidad de testing**
   - CLI ideal para pruebas rápidas
   - No requiere navegador

## 📞 Soporte

Para más información:
- Ver documentación en `../edge/Private_Docs/`
- Revisar logs en `../edge/edge.log`
- Consultar código fuente (bien comentado)
