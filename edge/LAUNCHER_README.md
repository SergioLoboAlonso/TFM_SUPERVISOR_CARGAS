# 🚀 Edge Layer Launcher - Guía de Uso

## Inicio Rápido

### macOS
1. **Doble clic** en `start_edge_gui.command`
2. Selecciona el modo de ejecución:
   - **1) Producción**: Sin debug, rendimiento óptimo
   - **2) Debug**: Logs detallados, sin auto-reload
   - **3) Desarrollo**: Logs + auto-reload automático al modificar archivos

### Linux
```bash
./start_edge_gui.command
```

### Windows
Usa `start_edge_gui.bat` (próximamente) o:
```cmd
python src/app.py
```

## Modos de Ejecución

### 1. Modo Producción
- ✅ Mejor rendimiento
- ✅ Sin logs de debug innecesarios
- ❌ Sin auto-reload (requiere reinicio manual)
- **Usa este modo para**: Operación normal, demostraciones

### 2. Modo Debug
- ✅ Logs detallados de todas las operaciones
- ✅ Información de debugging en terminal
- ❌ Sin auto-reload (requiere reinicio manual)
- **Usa este modo para**: Diagnóstico de problemas, análisis de comportamiento

### 3. Modo Desarrollo (Recomendado para programar)
- ✅ Logs detallados
- ✅ **Auto-reload**: El servidor se reinicia automáticamente cuando modificas archivos `.py`
- ✅ No necesitas detener/reiniciar manualmente
- ⚠️  Ligero overhead de performance (watchdog monitoreando archivos)
- **Usa este modo para**: Desarrollo activo, pruebas rápidas de cambios

## Auto-Reload: Cómo Funciona

En **Modo Desarrollo**:
1. El servidor monitorea todos los archivos `.py` en `edge/src/`
2. Cuando guardas un archivo modificado:
   ```
   📝 Archivo modificado: /path/to/file.py
   🔄 Recargando servidor...
   === Iniciando Edge Layer ===
   ```
3. El servidor se reinicia automáticamente con los nuevos cambios
4. No pierdes la conexión serie ni el estado de dispositivos descubiertos

**Archivos monitoreados**:
- `src/app.py`
- `src/modbus_master.py`
- `src/device_manager.py`
- `src/polling_service.py`
- `src/data_normalizer.py`
- `src/config.py`
- Cualquier archivo `.py` en `src/`

**NO requiere reinicio**:
- Cambios en templates HTML (`templates/*.html`)
- Cambios en CSS/JS (`static/*`)
- Cambios en `requirements.txt`

## Requisitos

### Primera Ejecución
El launcher verifica e instala automáticamente:
- ✅ Python 3.8+
- ✅ Entorno virtual (`venv/`)
- ✅ Dependencias (`requirements.txt`)

Si falta Python:
```bash
# macOS
brew install python3

# Ubuntu/Debian
sudo apt install python3 python3-venv

# Windows
# Descargar de https://www.python.org
```

### Dependencias Principales
```
Flask==3.0.0
Flask-SocketIO==5.3.5
pymodbus==3.5.4
pyserial==3.5
watchdog==3.0.0  # Para auto-reload
```

## Acceso a la Interfaz Web

Una vez iniciado el servidor:

```
✓ Python encontrado: 3.12.0
▶ Modo: Desarrollo (auto-reload)

════════════════════════════════════════════════════════════
   Iniciando Edge Layer...
════════════════════════════════════════════════════════════

  Puerto serie: /dev/tty.usbmodem5A300455411
  Baudrate:     115200
  Web UI:       http://192.168.0.23:8080  ← Abre en navegador
  Debug:        ON
  Auto-reload:  ON

Presiona CTRL+C para detener el servidor
```

### Páginas Disponibles
- **Dashboard**: `http://192.168.0.23:8080/`
- **Configuración**: `http://192.168.0.23:8080/config`
- **Polling**: `http://192.168.0.23:8080/polling`

## Detener el Servidor

**Método 1**: Presiona `CTRL+C` en la terminal

**Método 2**: Cierra la ventana de terminal

**Método 3** (Si se bloquea):
```bash
# macOS/Linux
killall python3

# O busca el proceso
ps aux | grep app.py
kill -9 <PID>
```

## Troubleshooting

### "Python3 no encontrado"
```bash
# Verifica instalación
which python3
python3 --version

# Si no está instalado
brew install python3  # macOS
```

### "Puerto serie ocupado"
```bash
# Cierra otros programas usando el puerto
lsof | grep usbmodem

# O reinicia el Arduino (desconectar/conectar USB)
```

### "watchdog no instalado" (Modo desarrollo)
```bash
cd edge
source venv/bin/activate
pip install watchdog
```

### El auto-reload no funciona
- ✅ Verifica que estés en Modo Desarrollo (opción 3)
- ✅ Guarda el archivo con `Cmd+S` / `Ctrl+S`
- ✅ Verifica que sea un archivo `.py` en `src/`
- ✅ Revisa logs en terminal para mensajes de error

### "ModuleNotFoundError"
```bash
# Reinstala dependencias
cd edge
source venv/bin/activate
pip install -r requirements.txt
```

## Desarrollo Avanzado

### Modificar Puerto/Host
Edita `edge/src/config.py`:
```python
FLASK_HOST = '0.0.0.0'  # Todas las interfaces
FLASK_PORT = 8080       # Puerto web
```

### Logs Personalizados
En Modo Debug/Desarrollo, todos los logs aparecen en:
- Terminal (stdout)
- Archivo `edge/logs/edge.log` (próximamente)

### Variables de Entorno
Crea `edge/.env`:
```bash
MODBUS_PORT=/dev/tty.usbmodem5A300455411
MODBUS_BAUDRATE=115200
FLASK_DEBUG=1
```

## Próximas Mejoras

- [ ] Launcher para Windows (`.bat`)
- [ ] Selección automática de puerto serie
- [ ] Logs a archivo con rotación
- [ ] Configuración de watchdog (intervalos, filtros)
- [ ] Modo headless (sin terminal, en background)
- [ ] Instalador con icono en macOS

## Soporte

¿Problemas? Revisa:
1. Esta guía (LAUNCHER_README.md)
2. Guía técnica principal (`docs/guia_tecnica.md`)
3. Logs en terminal (modo debug)
4. Estado del Arduino (LED parpadeando)

---

**Creado por**: Sergio Lobo  
**Proyecto**: TFM Supervisor de Cargas  
**Última actualización**: 2025-11-03
