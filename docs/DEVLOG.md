# DEVLOG - Registro de Desarrollo TFM_SUPERVISOR_CARGAS

## 2025-11-24 - Migración Edge a Raspberry Pi

### Contexto
Sistema IoT de tres capas (firmware Arduino, edge Python, infra Docker) para supervisión de cargas industriales con Modbus RTU y FIWARE. Se decidió migrar el sistema Edge de desarrollo local (Mac) a despliegue en Raspberry Pi para emular entorno productivo.

### Trabajo Realizado

#### 1. Estabilización Firmware (previo)
- **Problema**: Arduino UNO (2KB RAM) colgaba al calcular estadísticas rolling de sensor de viento en dispositivo.
- **Solución**: Eliminadas estadísticas en firmware; registros Modbus reservados devuelven 0; cálculos se harán en Edge.
- **Registros**: 27 input registers Modbus RTU @115200 baud; stats en 0x0220-0x0229 reservados.
- **Archivos**: `firmware/lib/ModbusRTU/src/registersModbus.cpp`, `firmware/include/registersModbus.h`

#### 2. Soporte Multi-Dispositivo
- **Objetivo**: Cargar firmware en segundo Arduino UNO (clon CH340).
- **Solución**: Creado entorno PlatformIO `[env:uno_clon]` con:
  - `UNIT_ID=16` (distinto del principal)
  - `upload_port=/dev/cu.usbserial-1430` (puerto explícito)
  - `-DMPU6050_ENABLED=0` (clon sin sensor MPU6050)
- **Archivo**: `platformio.ini`
- **Comando**: `pio run -e uno_clon -t upload`

#### 3. Limpieza Git
- **Problema**: Carpeta `edge_backup/` rastreada por error; muchos archivos duplicados.
- **Solución**:
  1. Añadido `edge_backup/` a `.gitignore`
  2. `git rm -r --cached edge_backup`; commit "Stop tracking edge_backup directory"
  3. Purgado historial completo con `git-filter-repo --path edge_backup --invert-paths --force`
  4. Force-push a `origin/main`
- **Nota**: Compañeros deben hacer `git fetch origin && git reset --hard origin/main`

#### 4. Configuración Remote Development (VS Code)
- **Objetivo**: Programar desde Mac, ejecutar en Raspberry vía Remote-SSH.
- **Archivos creados**:
  - `.vscode/launch.json`: Debug config "Python: Edge (Remote)" apuntando a `edge/src/app.py` con `envFile` edge/.env
  - `.vscode/tasks.json`: Tareas "Edge: Create venv", "Edge: Install deps", "Edge: Run"
  - `.vscode/settings.json`: Python interpreter `edge/venv/bin/python`, pytest en `edge/tests`
- **SSH Config** (Mac `~/.ssh/config`):
  ```
  Host raspi
      HostName <IP_RASPBERRY>
      User edge_sergio
      IdentityFile ~/.ssh/id_rsa
  ```

#### 5. Setup Raspberry Pi
- **Usuario**: `edge_sergio` (creado; añadido a grupos `sudo,dialout,gpio,i2c,spi`)
- **Repo**: Clonado en `/home/edge_sergio/Desktop/TFM_SUPERVISOR_CARGAS`
- **Python**: Debian Trixie requiere `python3-full` para venv (PEP 668)
- **Dependencias sistema**:
  ```bash
  sudo apt-get install -y python3-full python3-venv python3-pip build-essential python3-dev
  ```
- **Venv Edge**:
  ```bash
  cd ~/Desktop/TFM_SUPERVISOR_CARGAS/edge
  rm -rf venv  # si existe corrupto
  python3 -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
  ```
- **Configuración `.env`** (edge/.env):
  ```env
  MODBUS_PORT=/dev/ttyUSB0
  MODBUS_BAUDRATE=115200
  MODBUS_TIMEOUT=1.0
  FLASK_HOST=0.0.0.0
  FLASK_PORT=8080
  LOG_LEVEL=INFO
  ```
- **Permisos puerto serie**:
  ```bash
  sudo usermod -aG dialout edge_sergio
  newgrp dialout  # o re-login
  ls -l /dev/ttyUSB0  # verificar: crw-rw---- root dialout
  ```

#### 6. Script Automatizado
- **Archivo**: `edge/setup_raspi.sh`
- **Propósito**: Instalación y configuración completa en Raspberry (buscar adaptador RS-485, crear venv, instalar deps, configurar .env).
- **Uso**:
  ```bash
  cd ~/Desktop/TFM_SUPERVISOR_CARGAS/edge
  chmod +x setup_raspi.sh
  ./setup_raspi.sh
  ```

### Estado Actual (Pendiente)
- [ ] **Terminar instalación Python deps** en Raspberry (requiere `python3-full`; venv corrupto debe recrearse)
- [ ] **Identificar adaptador RS-485**: Ejecutar `lsusb`, `ls -l /dev/tty*`, `dmesg | grep tty` para confirmar `/dev/ttyUSB0` o `/dev/ttyACM0`
- [ ] **Ejecutar Edge** en Raspberry: `python edge_v2.py` (o `app.py` según main)
- [ ] **Port Forwarding** en VS Code: Forward puerto 8080 para acceso web desde Mac
- [ ] **Systemd service** (opcional): Autostart Edge en boot

### Decisiones Técnicas
- **PlatformIO envs separados** en lugar de build flags globales (revertido tras prueba) para mejor control por dispositivo.
- **Rutas relativas** en configs VS Code (`edge/venv`, `edge/.env`) para portabilidad entre local y remoto.
- **Usuario dedicado** `edge_sergio` en Raspberry para aislar proyecto y permisos.
- **Git workflow**: Desarrollo en Mac, push a GitHub, pull en Raspberry; evitar duplicación de repos en misma máquina.

### Comandos Útiles

**Raspberry (setup Edge):**
```bash
cd ~/Desktop/TFM_SUPERVISOR_CARGAS/edge
source venv/bin/activate
python edge_v2.py  # o app.py
```

**Mac (upload firmware):**
```bash
cd ~/Desktop/MASTER\ UNIR/MASTER\ IOT/2\ SEMESTRE/TFM/TFM_SUPERVISOR_CARGAS
pio run -e uno -t upload          # dispositivo principal
pio run -e uno_clon -t upload     # clon
```

**Buscar adaptador RS-485 (Raspberry):**
```bash
lsusb
ls -l /dev/tty* | grep -E "(USB|ACM)"
ls -l /dev/serial/by-id/
dmesg | grep -i "tty\|usb" | tail -20
```

**VS Code Remote-SSH:**
- Connect: Shift+Cmd+P → "Remote-SSH: Connect to Host…" → `raspi`
- Open Folder: `/home/edge_sergio/Desktop/TFM_SUPERVISOR_CARGAS`
- Forward Port: Shift+Cmd+P → "Forward a Port" → 8080

### Referencias
- Firmware: `firmware/lib/ModbusRTU/`, `firmware/include/registersModbus.h`
- Edge: `edge/edge_v2.py`, `edge/requirements.txt`, `edge/README.md`
- Docs: `docs/protocolos/modbus.md`, `.github/copilot-instructions.md`
- PlatformIO: `platformio.ini` (root), `firmware/platformio.ini`
