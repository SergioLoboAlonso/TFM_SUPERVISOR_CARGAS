# Edge Modbus RTU + Web UI Identify

Módulo Edge mínimo en Python que:

- Lee periódicamente registros Modbus RTU (por USB‑RS485) del esclavo indicado (UNIT_ID).
- Expone una UI web local con un botón "Identify" que invoca la función Modbus 0x11 (Report Slave ID):
	- Dispara el parpadeo de identificación en el firmware por un tiempo por defecto.
	- Devuelve y muestra Vendor/Modelo/FW en la UI.
- No usa cloud; todo local.

## Requisitos

- Python 3.10+
- Adaptador USB‑RS485 conectado (ej.: `/dev/ttyUSB0`, `/dev/tty.usbserial-XXXX`, `COM3`).
- Dependencias Python (se instalan más abajo):
	- `pymodbus==3.6.6`, `pyserial`, `Flask`, `python-dotenv`.

## Instalación rápida

```bash
cd edge
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Si el editor avisa "No se ha podido resolver la importación ...", asegúrate de que VS Code está usando el intérprete de `.venv` (Python: Select Interpreter) o activa el venv antes de abrir la carpeta.

## Configuración (.env opcional)

Crea `edge/.env` (si no existe). Variables soportadas y valores por defecto:

- `MODBUS_PORT` → puerto serie; auto‑detección si no se define (macOS: `/dev/tty.usb*`, Linux: `/dev/ttyUSB*`, Windows: `COM3`).
- `MODBUS_BAUD` → baudios (por defecto `115200`).
- `UNIT_ID` → dirección Modbus del esclavo (por defecto `1`).
- `POLL_MS` → periodo de sondeo en milisegundos (por defecto `200`).
- `HOST` → host de Flask (por defecto `0.0.0.0`).
- `PORT` → puerto HTTP (por defecto `8080`).

Ejemplo `edge/.env`:

```
MODBUS_PORT=/dev/tty.usbserial-XXXXX
MODBUS_BAUD=115200
UNIT_ID=1
POLL_MS=200
HOST=0.0.0.0
PORT=8080
```

## Ejecución

Ejecuta siempre desde la carpeta `edge/` (así encuentra `templates/` y el `.env`):

```bash
cd edge
source .venv/bin/activate
python edge.py
```

- UI: http://0.0.0.0:8080
- La página se actualiza ~cada 1 s; puedes cambiar `UNIT_ID` y pulsar "Aplicar".
- Botón "Identify (0x11)" → solicita Identify como operación propia (0x11): el firmware decide la duración y responde con la cadena de identidad.

## Endpoints

- `GET /` → HTML mínimo con tablas y controles.
- `GET /state` → JSON con el último estado leído: holding e inputs, flags de conexión y errores.
- `POST /identify` → body JSON `{ "unit": <id> }`; llama a 0x11 (Report Slave ID) y responde `{ ok, info: { slaveId, running, text } }`.

Pruebas rápidas con curl (opcional):

```bash
# Obtener estado
curl -s http://localhost:8080/state | jq

# Identify (0x11) para UNIT 1
curl -s -X POST http://localhost:8080/identify \
	-H 'Content-Type: application/json' \
	-d '{"unit":1}'
```

## Qué registra el Edge

- Holding info 0x0000..0x0009 (10 regs): vendor, product, hw/fw, unit_echo, caps, uptime L/H, status, errors.
- Input regs 0x0000..0x000B (12 regs): ángulos X/Y (mdeg), temp (mC), acc x/y/z (mg), gyr x/y/z (mdps), sample L/H, flags.

## Notas de implementación (resumen)

- Cliente: `ModbusSerialClient` (pymodbus 3.6.x). En serie, el framer RTU es el comportamiento por defecto.
- Lectura periódica en hilo: `read_input_registers()` y `read_holding_registers()` con `unit=UNIT_ID`.
- Estado compartido para la UI, con `connected`, `last_error`, `holding`, `input`.
- Reconexión automática en caso de error.

## Solución de problemas

- "Address already in use" al arrancar Flask:
	- Otro proceso usa el puerto `PORT` (8080). Cambia `PORT` en `.env` o cierra el proceso previo.
	- Si se quedó colgado, puedes matar por puerto (macOS):
		```bash
		lsof -i :8080
		kill -9 <PID>
		```

- Timeout o lecturas erróneas:
	- Verifica `MODBUS_PORT`, cableado, resistencia de terminación (120 Ω), DE/RE del MAX485, tierra común.
	- Asegúrate de que `UNIT_ID` es el correcto. Recuerda: los broadcasts (UNIT 0) no obtienen respuesta.
	- Revisa baudios/paridad (por defecto 115200 8N1).

- "Module not found" (flask, pymodbus):
	- Activa el venv (`source .venv/bin/activate`) e instala `pip install -r requirements.txt`.
	- En VS Code, selecciona el intérprete del venv para evitar avisos del linter.

- macOS: permisos de puerto serie
	- Normalmente no hace falta sudo; si hay problemas, comprueba grupo/permisos del dispositivo en `/dev`.

## Estructura

```
edge/
	edge.py                # app principal (poll + Flask)
	templates/
		index.html           # UI mínima
	requirements.txt       # dependencias
	.env                   # (opcional) variables de entorno locales
```

---

¿Quieres que prepare un Dockerfile para este módulo edge o una unidad systemd para arranque automático? Puedo añadirlo como extra cuando lo necesites.
