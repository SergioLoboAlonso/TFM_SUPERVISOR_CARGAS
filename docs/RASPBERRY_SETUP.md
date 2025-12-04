# Raspberry Pi Setup - Edge Layer

## Requisitos Previos
- Raspberry Pi con Debian Trixie (o similar)
- Acceso SSH configurado
- Adaptador USB RS-485 conectado
- Arduino(s) con firmware cargado en bus RS-485

## 1. Preparación Usuario

```bash
# Crear usuario (si no existe)
sudo adduser edge_sergio

# Añadir a grupos necesarios
sudo usermod -aG sudo,dialout,gpio,i2c,spi edge_sergio

# Cambiar a usuario
su - edge_sergio
```

## 2. Clonar Repositorio

```bash
# HTTPS (requiere token si privado)
cd ~/Desktop
git clone https://github.com/SergioLoboAlonso/TFM_SUPERVISOR_CARGAS.git

# O SSH (requiere llave configurada)
git clone git@github.com:SergioLoboAlonso/TFM_SUPERVISOR_CARGAS.git
```

### Configurar Git (primera vez)
```bash
git config --global user.name "Tu Nombre"
git config --global user.email "tu.email@example.com"
```

### SSH Key para GitHub (opcional)
```bash
ssh-keygen -t ed25519 -C "tu.email@example.com"
cat ~/.ssh/id_ed25519.pub  # Copiar a GitHub Settings → SSH keys
ssh -T git@github.com      # Verificar
```

## 3. Instalar Dependencias Sistema

```bash
sudo apt-get update
sudo apt-get install -y \
    python3-full \
    python3-venv \
    python3-pip \
    build-essential \
    python3-dev \
    git
```

**Nota**: `python3-full` es **obligatorio** en Debian Trixie/Bookworm por PEP 668.

## 4. Crear Entorno Virtual Python

```bash
cd ~/Desktop/TFM_SUPERVISOR_CARGAS/edge

# Crear venv
python3 -m venv venv

# Activar
source venv/bin/activate

# Actualizar pip
pip install --upgrade pip

# Instalar dependencias
pip install -r requirements.txt
```

### Dependencias esperadas
- Flask 3.0.0
- Flask-SocketIO 5.3.5
- eventlet 0.33.3
- pymodbus 3.5.4
- pyserial 3.5
- python-dotenv
- coloredlogs
- watchdog
- pytest, pytest-mock

## 5. Configurar Variables de Entorno

```bash
cd ~/Desktop/TFM_SUPERVISOR_CARGAS/edge

# Crear .env
nano .env
```

**Contenido mínimo:**
```env
MODBUS_PORT=/dev/ttyUSB0
MODBUS_BAUDRATE=115200
MODBUS_TIMEOUT=1.0
MODBUS_DISCOVERY_TIMEOUT=2.0
FLASK_HOST=0.0.0.0
FLASK_PORT=8080
LOG_LEVEL=INFO
```

Guarda (Ctrl+O, Enter, Ctrl+X).

## 6. Identificar Adaptador RS-485

```bash
# Listar dispositivos USB
lsusb

# Buscar dispositivos serie
ls -l /dev/tty* | grep -E "(USB|ACM)"

# Ver por ID
ls -l /dev/serial/by-id/

# Mensajes kernel recientes
dmesg | grep -i "tty\|usb\|serial" | tail -20
```

**Dispositivos comunes:**
- `/dev/ttyUSB0` - Adaptadores FTDI, CH340, CP210x
- `/dev/ttyACM0` - Dispositivos CDC ACM (algunos Arduino)

**Actualizar `.env`** si el puerto es distinto a `/dev/ttyUSB0`.

## 7. Permisos Puerto Serie

```bash
# Añadir usuario a grupo dialout
sudo usermod -aG dialout edge_sergio

# Aplicar cambios (opción 1: re-login)
exit
ssh edge_sergio@<IP_RASPBERRY>

# Aplicar cambios (opción 2: newgrp)
newgrp dialout

# Verificar grupos
groups
# Debe aparecer: edge_sergio dialout ...

# Verificar permisos dispositivo
ls -l /dev/ttyUSB0
# Esperado: crw-rw---- 1 root dialout ...
```

### Permiso temporal (solo para pruebas)
```bash
sudo chmod 666 /dev/ttyUSB0
```

**Nota**: Este permiso se pierde al desconectar/reconectar el USB.

## 8. Ejecutar Edge (Manual)

```bash
cd ~/Desktop/TFM_SUPERVISOR_CARGAS/edge
source venv/bin/activate

# Ejecutar
python edge_v2.py
# O si usas app.py como main:
# python app.py
```

**Salida esperada:**
```
INFO - Modbus client initialized on /dev/ttyUSB0 @ 115200
INFO - Starting discovery...
INFO - Device found: UnitID=1, Alias=...
INFO - Flask app running on http://0.0.0.0:8080
```

**Acceso web** (desde Mac): `http://<IP_RASPBERRY>:8080`

## 9. VS Code Remote-SSH (Desarrollo)

### En Mac (`~/.ssh/config`):
```
Host raspi
    HostName <IP_RASPBERRY>
    User edge_sergio
    IdentityFile ~/.ssh/id_rsa
```

### Conectar:
1. VS Code: Shift+Cmd+P → "Remote-SSH: Connect to Host…"
2. Seleccionar `raspi`
3. File → Open Folder → `/home/edge_sergio/Desktop/TFM_SUPERVISOR_CARGAS`

### Port Forwarding:
- Shift+Cmd+P → "Forward a Port" → `8080`
- Acceder desde Mac: `http://localhost:8080`

### Ejecutar/Depurar:
- **Tasks**: Terminal → Run Task → "Edge: Run"
- **Debug**: Run → Start Debugging → "Python: Edge (Remote)"

## 10. Systemd Service (Autostart)

```bash
sudo nano /etc/systemd/system/tfm-edge.service
```

**Contenido:**
```ini
[Unit]
Description=TFM Edge Service
After=network.target

[Service]
Type=simple
User=edge_sergio
WorkingDirectory=/home/edge_sergio/Desktop/TFM_SUPERVISOR_CARGAS/edge
Environment="PATH=/home/edge_sergio/Desktop/TFM_SUPERVISOR_CARGAS/edge/venv/bin"
ExecStart=/home/edge_sergio/Desktop/TFM_SUPERVISOR_CARGAS/edge/venv/bin/python edge_v2.py
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
```

**Activar:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable tfm-edge.service
sudo systemctl start tfm-edge.service

# Ver logs
journalctl -u tfm-edge -f
```

**Control:**
```bash
sudo systemctl status tfm-edge
sudo systemctl stop tfm-edge
sudo systemctl restart tfm-edge
```

## 11. Script Automatizado

```bash
cd ~/Desktop/TFM_SUPERVISOR_CARGAS/edge
chmod +x setup_raspi.sh
./setup_raspi.sh
```

Este script ejecuta pasos 3-7 automáticamente.

## Troubleshooting

### Error: `externally-managed-environment`
**Solución**: Instalar `python3-full` y usar venv (no instalar con pip global).

### Error: `Permission denied` en `/dev/ttyUSB0`
**Solución**: Añadir usuario a `dialout`, re-login o `newgrp dialout`.

### Error: `No module named 'serial'`
**Solución**: Activar venv (`source venv/bin/activate`) antes de ejecutar.

### Error: Venv corrupto (errno 2)
**Solución**:
```bash
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Adaptador no detectado
**Verificar**:
1. USB conectado físicamente
2. `lsusb` muestra dispositivo
3. Driver cargado: `lsmod | grep -E "ftdi|ch341|cp210x"`
4. Probar otro puerto USB

### Flask no accesible desde Mac
**Verificar**:
1. `FLASK_HOST=0.0.0.0` en `.env` (no `127.0.0.1`)
2. Firewall Raspberry: `sudo ufw allow 8080` (si `ufw` activo)
3. Port forwarding en VS Code configurado

## Referencias
- Repo: https://github.com/SergioLoboAlonso/TFM_SUPERVISOR_CARGAS
- Edge README: `edge/README.md`
- Modbus protocol: `docs/protocolos/modbus.md`
- Copilot instructions: `.github/copilot-instructions.md`
- DEVLOG: `docs/DEVLOG.md`
