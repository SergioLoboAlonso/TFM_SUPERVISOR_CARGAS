"""
edge/edge.py — Módulo Edge mínimo (Modbus RTU por USB‑RS485 + UI web Identify)

Objetivo
--------
- Leer periódicamente:
    - Input Registers 0x0000..0x000B (12 registros).
    - Holding "info" 0x0000..0x0009 (10 registros).
- Exponer una UI web (Flask) con un botón "Identify" que escribe el holding
    HR_CMD_IDENT_SECS (0x0013) con un valor en segundos (0 = stop).

Entorno / Dependencias
----------------------
- Python 3.10+
- Librerías: pymodbus==3.6.6, pyserial, Flask, python-dotenv

Configuración por entorno (.env opcional)
----------------------------------------
- MODBUS_PORT (p.ej. /dev/ttyUSB0, /dev/tty.usbserial-XXXX, COM3)
- MODBUS_BAUD (por defecto 115200)
- UNIT_ID (por defecto 1)
- POLL_MS (periodo de sondeo; por defecto 200 ms)
- HOST (host para Flask; por defecto 0.0.0.0)
- PORT (puerto HTTP; por defecto 8080)

Notas de implementación
-----------------------
- El cliente Modbus serie usa RTU por defecto en pymodbus 3.6.x; no se pasa
    el parámetro "method" (esta versión no lo acepta). Se configura con port,
    baudrate, parity, stopbits, bytesize, timeout.
- Se mantiene un estado compartido en memoria con el último muestreo.
- En caso de error de lectura/conexión se marca estado de error y se intenta
    reconectar.
"""
# edge/edge.py — Edge mínimo Modbus RTU + UI Identify (pymodbus 3.x + Flask)
import os        # acceso a variables de entorno y ruta de sistema
import time      # temporizaciones (sleep) y marcas de tiempo
import threading # hilo para el sondeo Modbus en paralelo con Flask
import glob      # detección sencilla del puerto serie por patrón
import logging   # trazas y diagnóstico
from collections import deque  # buffer circular de eventos

from flask import Flask, jsonify, render_template, request  # micro‑framework web
from dotenv import load_dotenv  # carga de variables desde .env
from pymodbus.client import ModbusSerialClient  # cliente Modbus RTU sobre puerto serie
import importlib  # importación dinámica para compatibilidad de versiones

# -----------------------------
# Config
# -----------------------------
load_dotenv()  # carga variables de un archivo .env si existe en el directorio actual

# Logging básico (ajustable con EDGE_DEBUG=1)
EDGE_DEBUG = os.getenv("EDGE_DEBUG", "0") == "1"
logging.basicConfig(level=logging.DEBUG if EDGE_DEBUG else logging.INFO,
                    format='%(asctime)s %(levelname)s %(name)s: %(message)s')
log = logging.getLogger("edge")
for n in ("pymodbus", "pymodbus.client", "pymodbus.transaction", "serial"):
    logging.getLogger(n).setLevel(logging.DEBUG if EDGE_DEBUG else logging.INFO)

# Buffer circular de diagnóstico de alto nivel
diag_log = deque(maxlen=200)
def log_event(kind, **fields):
    evt = {"ts": time.time(), "kind": kind}
    evt.update(fields)
    diag_log.append(evt)
    if EDGE_DEBUG:
        log.debug("%s %s", kind, fields)

def detect_default_port():
    """Intenta adivinar un puerto serie razonable por plataforma.
    - macOS: /dev/tty.usb*
    - Linux: /dev/ttyUSB*
    - Windows: COMx (fallback COM3)
    """
    cand = []  # lista de candidatos encontrados por patrón
    cand += glob.glob("/dev/tty.usb*")  # típicos en macOS
    cand += glob.glob("/dev/ttyUSB*")   # típicos en Linux
    return cand[0] if cand else ("COM3" if os.name == "nt" else "/dev/ttyUSB0")

# Variables de configuración (con valores por defecto)
PORT = os.getenv("MODBUS_PORT", detect_default_port())   # puerto serie (p.ej., /dev/ttyUSB0)
BAUD = int(os.getenv("MODBUS_BAUD", "115200"))         # baudios Modbus RTU
UNIT_DEFAULT = int(os.getenv("UNIT_ID", "1"))           # UNIT_ID por defecto (esclavo)
POLL_MS = int(os.getenv("POLL_MS", "200"))              # periodo de sondeo en milisegundos
HOST = os.getenv("HOST", "0.0.0.0")                     # host de Flask
PORT_HTTP = int(os.getenv("PORT", "8080"))              # puerto HTTP de Flask

# Mapa de registros (base 0)
# - HR (Holding) info 0x0000..0x0009: metadatos de dispositivo/uptime/estado
# - IR (Input)      0x0000..0x000B: telemetría (ángulos, temp, acc, gyro, sample, flags)
HR = dict(DEV_VENDOR_ID=0x0000, DEV_PRODUCT_ID=0x0001, DEV_HW_VERSION=0x0002,
          DEV_FW_VERSION=0x0003, DEV_UNIT_ID=0x0004, DEV_CAPS=0x0005,
          DEV_UPTIME_LO=0x0006, DEV_UPTIME_HI=0x0007, DEV_STATUS=0x0008,
          DEV_ERRORS=0x0009, CMD_IDENT_SECS=0x0013)
IR = dict(ANGLE_X=0x0000, ANGLE_Y=0x0001, TEMP=0x0002,
          ACC_X=0x0003, ACC_Y=0x0004, ACC_Z=0x0005,
          GYR_X=0x0006, GYR_Y=0x0007, GYR_Z=0x0008,
          SAMPLE_LO=0x0009, SAMPLE_HI=0x000A, FLAGS=0x000B)

# Estado compartido expuesto a la UI
# - "connected": True si la conexión Modbus está abierta y las lecturas responden
# - "last_error": texto del último error para diagnosticar fallos puntuales
state = {
    "unit": UNIT_DEFAULT,  # UNIT_ID actual usado en lecturas/escrituras
    "port": PORT,          # puerto serie actual
    "baud": BAUD,          # baudios
    "connected": False,
    "last_error": None,
    "holding": {},         # último snapshot de HR info (dict de campos sencillos)
    "input": {}            # último snapshot de IR (dict con telemetrías)
}

# Cliente Modbus RTU (serie)
# - En pymodbus 3.6.x, el framer RTU es el comportamiento por defecto en cliente serie.
# - Parámetros típicos de 8N1 y un timeout prudente para evitar bloqueos largos.
cli = ModbusSerialClient(
    port=PORT,
    baudrate=BAUD,
    parity="N",
    stopbits=1,
    bytesize=8,
    timeout=1.5,
    retries=2,
    retry_on_empty=True,
)

# Serializa el acceso al cliente Modbus (no es thread-safe)
cli_lock = threading.Lock()
poll_enabled = True  # permite pausar el sondeo para aislar pruebas manuales

def to_s32(lo, hi):
    """Compone un entero de 32 bits a partir de dos words (lo + hi).
    Modbus expone registros de 16 bits; algunos contadores 32 bits vienen en L/H.
    """
    return (hi << 16) | lo

# -----------------------------
# Poll Modbus en hilo
# -----------------------------
def poller():
    """Hilo de sondeo Modbus.
    - Garantiza conexión (connect) con reintentos.
    - Lee IR (12 regs) y HR info (10 regs) para la UNIT_ID indicada.
    - Actualiza el diccionario `state` con los últimos valores.
    - En caso de error: marca `last_error`, cierra cliente y re‑inicializa.
    """
    global cli, state
    while True:
        try:
            if not poll_enabled:
                time.sleep(POLL_MS / 1000.0)
                continue
            if not state["connected"]:                 # si no estamos conectados
                with cli_lock:
                    state["connected"] = cli.connect()  # pymodbus abre el puerto serie
                if not state["connected"]:
                    state["last_error"] = "connect_failed"
                    time.sleep(1)
                    continue

            # Lecturas Modbus: IR (0x0000..0x000B) y HR info (0x0000..0x0009)
            # - read_input_registers(offset, count, unit=UNIT_ID)
            # - read_holding_registers(offset, count, unit=UNIT_ID)
            # Respuesta pymodbus: objeto con .isError() y .registers (lista de ints)
            with cli_lock:
                log_event("read_input_registers:req", unit=state["unit"], start=IR["ANGLE_X"], count=12)
                r_ir = cli.read_input_registers(IR["ANGLE_X"], 12, unit=state["unit"])
                log_event("read_input_registers:res", ok=(not getattr(r_ir, "isError", lambda: True)()),
                          type=str(type(r_ir)), payload=getattr(r_ir, "registers", None))
                log_event("read_holding_registers:req", unit=state["unit"], start=HR["DEV_VENDOR_ID"], count=10)
                r_hr = cli.read_holding_registers(HR["DEV_VENDOR_ID"], 10, unit=state["unit"])
                log_event("read_holding_registers:res", ok=(not getattr(r_hr, "isError", lambda: True)()),
                          type=str(type(r_hr)), payload=getattr(r_hr, "registers", None))

            if not getattr(r_ir, "isError", lambda: True)():
                ir = r_ir.registers  # lista de 12 registros (int de 0..65535)
                state["input"] = {
                    "angles_mdeg": {"x": ir[0], "y": ir[1]},
                    "temp_mC": ir[2],
                    "acc_mg": {"x": ir[3], "y": ir[4], "z": ir[5]},
                    "gyr_mdps": {"x": ir[6], "y": ir[7], "z": ir[8]},
                    "sample_count": to_s32(ir[9], ir[10]),
                    "flags": ir[11],
                }
            else:
                state["last_error"] = f"ir:{r_ir}"  # error Modbus (exception response)

            if not getattr(r_hr, "isError", lambda: True)():
                hr = r_hr.registers  # lista de 10 registros para info de dispositivo
                state["holding"] = {
                    "vendor": hr[0], "product": hr[1],
                    "hw": hr[2], "fw": hr[3],
                    "unit_echo": hr[4], "caps": hr[5],
                    "uptime_s": to_s32(hr[6], hr[7]),
                    "status": hr[8], "errors": hr[9],
                }
            else:
                state["last_error"] = f"hr:{r_hr}"

        except Exception as e:
            state["connected"] = False               # caída de conexión o fallo de lectura
            state["last_error"] = str(e)             # guardamos diagnóstico textual
            log_event("error", where="poller", err=str(e))
            try:
                with cli_lock:
                    cli.close()  # cierra el puerto; si ya está cerrado puede lanzar
            except Exception:
                pass
            time.sleep(1)
            with cli_lock:
                cli.__init__(  # reconfigura el cliente (mismos parámetros)
                    port=PORT,
                    baudrate=BAUD,
                    parity="N",
                    stopbits=1,
                    bytesize=8,
                    timeout=1.0,
                )
        time.sleep(POLL_MS / 1000.0)  # ritmo de sondeo (no bloquear la CPU)

# -----------------------------
# Web
# -----------------------------
app = Flask(__name__, template_folder="templates", static_folder="static")  # instancia de la app web

@app.route("/")
def idx():
    """Página principal (HTML) con UI mínima.
    - Muestra tablas con últimos valores (vía JS hace polling a /state).
    - Controles para UNIT_ID y acción Identify.
    """
    return render_template("index.html")

@app.route("/state")
def get_state():
    """Devuelve el estado actual en JSON (usado por la UI para refrescar)."""
    return jsonify(state)  # Flask convierte dict -> JSON y añade cabeceras adecuadas

@app.route("/diag/logs")
def diag_logs():
    """Devuelve los últimos eventos de diagnóstico (orden cronológico)."""
    return jsonify(list(diag_log))

@app.route("/diag/poll", methods=["POST"]) 
def diag_poll_toggle():
    """Activa/desactiva el sondeo periódico para aislar pruebas manuales.
    Body: { enable: true|false }
    """
    global poll_enabled
    try:
        data = request.get_json(force=True)
        enable = bool(data.get("enable", True))
        poll_enabled = enable
        log_event("poll_enabled", value=poll_enabled)
        return jsonify(ok=True, enabled=poll_enabled)
    except Exception as e:
        return jsonify(ok=False, err=str(e)), 500

@app.route("/identify", methods=["POST"])
def identify():
    """Acción Identify unificada: invoca 0x11 (Report Slave ID) en el esclavo.
    Request JSON: { "unit": <id> }  (seconds es ignorado; la duración la decide el firmware)
    Respuesta: { ok: true, info: { vendor, model, fw, slaveId, running } } o error.
    """
    try:
        data = request.get_json(force=True)
        unit = int(data.get("unit", state["unit"]))

        # Preferir API específica si existe; si no, usar execute con Request
        ascii_info = None
        slave_id = None
        running = None

        if hasattr(cli, "report_slave_id"):
            with cli_lock:
                log_event("report_slave_id:req", unit=unit)
                res = cli.report_slave_id(unit=unit)
        else:
            # Intentar vía execute() con petición explícita
            try:
                diag = importlib.import_module("pymodbus.diag_message")
                RequestCls = getattr(diag, "ReportSlaveIdRequest", None)
            except Exception:
                RequestCls = None
            if RequestCls is None or not hasattr(cli, "execute"):
                return jsonify(ok=False, err="ReportSlaveId no soportado por pymodbus"), 400
            with cli_lock:
                log_event("report_slave_id:req-exec", unit=unit)
                try:
                    res = cli.execute(RequestCls(unit=unit))
                except TypeError:
                    res = cli.execute(RequestCls())

        if getattr(res, "isError", lambda: True)():
            err = str(res)
            code = getattr(res, "exception_code", None)
            log_event("report_slave_id:err", err=err, exception_code=code)
            return jsonify(ok=False, err=err, exception_code=code), 400

        # Intentar extraer el bloque de información (bytes) del response
        payload = None
        for attr in ("information", "data", "message"):
            val = getattr(res, attr, None)
            if val is not None:
                payload = val
                break

        if isinstance(payload, list):
            payload = bytes(payload)
        if isinstance(payload, (bytes, bytearray)) and len(payload) >= 2:
            slave_id = payload[0]
            running = (payload[1] == 0xFF)
            try:
                ascii_info = payload[2:].decode("ascii", errors="ignore")
            except Exception:
                ascii_info = None

        state["unit"] = unit
        log_event("report_slave_id:ok", slaveId=slave_id, running=running, text=ascii_info)
        return jsonify(ok=True, info={
            "slaveId": slave_id,
            "running": running,
            "text": ascii_info,
        })
    except Exception as e:
        return jsonify(ok=False, err=str(e)), 500

@app.route("/identify/trigger", methods=["POST"])
def identify_trigger():
    """Acción Identify propietaria: invoca 0x41 (trigger + info).
    Request JSON: { "unit": <id> }
    Respuesta: { ok: true, info: { slaveId, running, text } } o error.
    """
    try:
        data = request.get_json(force=True)
        unit = int(data.get("unit", state["unit"]))

        # Construir una petición personalizada con function_code 0x41
        try:
            pdu = importlib.import_module("pymodbus.pdu")
            ModbusRequest = getattr(pdu, "ModbusRequest")
        except Exception:
            ModbusRequest = None
        if ModbusRequest is None or not hasattr(cli, "execute"):
            return jsonify(ok=False, err="Custom request 0x41 no soportada por pymodbus"), 400

        class IdentifyBlinkAndInfoRequest(ModbusRequest):
            function_code = 0x41
            def __init__(self):
                super().__init__()
            def encode(self):
                return b""  # sin datos
            def decode(self, data):
                # La respuesta se maneja como payload genérico en el objeto devuelto
                self.data = data

        req = IdentifyBlinkAndInfoRequest()
        # Intentar pasar el unit de forma explícita (3.x permite kwarg unit)
        try:
            with cli_lock:
                log_event("identify_0x41:req", unit=unit)
                res = cli.execute(req, unit=unit)
        except TypeError:
            # Fallback: establecer atributo unit_id en la request y ejecutar sin kwarg
            try:
                setattr(req, "unit_id", unit)
            except Exception:
                pass
            with cli_lock:
                log_event("identify_0x41:req-fallback", unit=unit)
                res = cli.execute(req)
        if getattr(res, "isError", lambda: True)():
            err = str(res)
            code = getattr(res, "exception_code", None)
            log_event("identify_0x41:err", err=err, exception_code=code)
            return jsonify(ok=False, err=err, exception_code=code), 400

        payload = None
        for attr in ("information", "data", "message"):
            val = getattr(res, attr, None)
            if val is not None:
                payload = val
                break
        if isinstance(payload, list):
            payload = bytes(payload)

        slave_id = None
        running = None
        ascii_info = None
        if isinstance(payload, (bytes, bytearray)) and len(payload) >= 2:
            slave_id = payload[0]
            running = (payload[1] == 0xFF)
            try:
                ascii_info = payload[2:].decode("ascii", errors="ignore")
            except Exception:
                ascii_info = None

        state["unit"] = unit
        log_event("identify_0x41:ok", slaveId=slave_id, running=running, text=ascii_info)
        return jsonify(ok=True, info={
            "slaveId": slave_id,
            "running": running,
            "text": ascii_info,
        })
    except Exception as e:
        return jsonify(ok=False, err=str(e)), 500

@app.route("/identify/seconds", methods=["POST"])
def identify_seconds():
    """Escribe el registro HR_CMD_IDENT_SECS (0x0013) con una duración personalizada.
    Request JSON: { unit: <id>, seconds: <n> }
    """
    try:
        data = request.get_json(force=True)
        unit = int(data.get("unit", state["unit"]))
        seconds = int(data.get("seconds", 0))

        addr = HR["CMD_IDENT_SECS"]
        with cli_lock:
            log_event("write_single:req", unit=unit, addr=addr, value=seconds)
            res = cli.write_register(addr, seconds, unit=unit)
        if getattr(res, "isError", lambda: True)():
            err = str(res)
            code = getattr(res, "exception_code", None)
            log_event("write_single:err", err=err, exception_code=code)
            return jsonify(ok=False, err=err, exception_code=code), 400
        state["unit"] = unit
        log_event("write_single:ok")
        return jsonify(ok=True)
    except Exception as e:
        return jsonify(ok=False, err=str(e)), 500

# -----------------------------
# Main
# -----------------------------
if __name__ == "__main__":
    # Arranca el hilo de sondeo Modbus y el servidor Flask.
    # - Hilo "daemon": finaliza automáticamente cuando el proceso principal termina.
    t = threading.Thread(target=poller, daemon=True)
    t.start()
    # Servidor HTTP accesible en http://HOST:PORT_HTTP
    app.run(host=HOST, port=PORT_HTTP)
