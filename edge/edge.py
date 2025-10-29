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
from contextlib import contextmanager

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
UNIT_DEFAULT = 1  # UNIT_ID inicial - el usuario puede cambiarlo dinámicamente desde la UI
AUTO_ALIGN_UNIT = (os.getenv("EDGE_AUTO_ALIGN_UNIT", "0") == "1")  # Alinear unit con HR_INFO_ID_UNIDAD tras lecturas exitosas
POLL_MS = int(os.getenv("POLL_MS", "200"))              # periodo de sondeo en milisegundos
HOST = os.getenv("HOST", "0.0.0.0")                     # host de Flask
PORT_HTTP = int(os.getenv("PORT", "8080"))              # puerto HTTP de Flask

# Mapa de registros (base 0)
# - HR (Holding) info 0x0000..0x0009: metadatos de dispositivo/uptime/estado
# - IR (Input)      0x0000..0x000B: telemetría (ángulos, temp, acc, gyro, sample, flags)
HR = dict(
    DEV_VENDOR_ID=0x0000, DEV_PRODUCT_ID=0x0001, DEV_HW_VERSION=0x0002,
    DEV_FW_VERSION=0x0003, DEV_UNIT_ID=0x0004, DEV_CAPS=0x0005,
    DEV_UPTIME_LO=0x0006, DEV_UPTIME_HI=0x0007, DEV_STATUS=0x0008,
    DEV_ERRORS=0x0009, CMD_IDENT_SECS=0x0013,
    VENDOR_LEN=0x0026, VENDOR0=0x0027, VENDOR1=0x0028, VENDOR2=0x0029, VENDOR3=0x002A,
    PRODUCT_LEN=0x002B, PRODUCT0=0x002C, PRODUCT1=0x002D, PRODUCT2=0x002E, PRODUCT3=0x002F,
    ALIAS_LEN=0x0030,
)
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
    "input": {},           # último snapshot de IR (dict con telemetrías)
    "poll_enabled": False,  # expone si el sondeo está activo
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
poll_enabled = True  # por defecto, polling activado
# Temporizador de pausa automática del sondeo
pause_timer = None
pause_lock = threading.Lock()

# Utilidad: ejecutar una operación Modbus con exclusión del poller y timeout temporal
@contextmanager
def modbus_exclusive(timeout=None):
    global poll_enabled
    prev_poll = poll_enabled
    poll_enabled = False  # pausa sondeo
    time.sleep(0.1)      # pequeña holgura para liberar el bus (guard time RS-485)
    prev_timeout = getattr(cli, "timeout", None)
    if timeout is not None:
        try:
            cli.timeout = timeout
        except Exception:
            pass
    try:
        with cli_lock:
            # Asegurar conexión por si el poller estaba desconectado
            if not state.get("connected", False):
                state["connected"] = cli.connect()
            yield
    finally:
        # Restaura timeout y reanuda el poller
        if timeout is not None and prev_timeout is not None:
            try:
                cli.timeout = prev_timeout
            except Exception:
                pass
        poll_enabled = prev_poll
        time.sleep(0.01)

# Descubrimiento tolerante de la clase ReportSlaveIdRequest en distintas versiones
def _get_report_slave_id_request_class():
    try:
        mod = importlib.import_module("pymodbus.other_message")
        cls = getattr(mod, "ReportSlaveIdRequest", None)
        if cls is not None:
            return cls
    except Exception:
        pass
    try:
        mod = importlib.import_module("pymodbus.diag_message")
        cls = getattr(mod, "ReportSlaveIdRequest", None)
        if cls is not None:
            return cls
    except Exception:
        pass
    return None

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
                # Leemos 10 registros estándar (sin extensiones de patch)
                log_event("read_holding_registers:req", unit=state["unit"], start=HR["DEV_VENDOR_ID"], count=10)
                r_hr = cli.read_holding_registers(HR["DEV_VENDOR_ID"], 10, unit=state["unit"])
                log_event("read_holding_registers:res", ok=(not getattr(r_hr, "isError", lambda: True)()),
                          type=str(type(r_hr)), payload=getattr(r_hr, "registers", None))
                # Intento de identidad extendida: 10 regs desde 0x0026 (len + 4 regs vendor + len + 4 regs product)
                log_event("read_holding_registers:req", unit=state["unit"], start=HR["VENDOR_LEN"], count=10)
                r_id = cli.read_holding_registers(HR["VENDOR_LEN"], 10, unit=state["unit"])
                log_event("read_holding_registers:res", ok=(not getattr(r_id, "isError", lambda: True)()),
                          type=str(type(r_id)), payload=getattr(r_id, "registers", None))
                # Alias: leer longitud (1 reg) y luego los datos necesarios (ceil(len/2) regs, máx 32)
                log_event("read_holding_registers:req", unit=state["unit"], start=HR["ALIAS_LEN"], count=1)
                r_alias_len = cli.read_holding_registers(HR["ALIAS_LEN"], 1, unit=state["unit"])
                log_event("read_holding_registers:res", ok=(not getattr(r_alias_len, "isError", lambda: True)()),
                          type=str(type(r_alias_len)), payload=getattr(r_alias_len, "registers", None))
                r_alias = None
                alias_words = 0
                if not getattr(r_alias_len, "isError", lambda: True)():
                    alen_val = (r_alias_len.registers or [0])[0] & 0xFFFF
                    if alen_val > 64:
                        alen_val = 64
                    alias_words = (alen_val + 1) // 2 if alen_val > 0 else 0
                    if alias_words > 0:
                        log_event("read_holding_registers:req", unit=state["unit"], start=HR["ALIAS_LEN"]+1, count=alias_words)
                        r_alias = cli.read_holding_registers(HR["ALIAS_LEN"]+1, alias_words, unit=state["unit"])
                        log_event("read_holding_registers:res", ok=(not getattr(r_alias, "isError", lambda: True)()),
                                  type=str(type(r_alias)), payload=getattr(r_alias, "registers", None))

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
                fw_val = hr[3]
                hw_val = hr[2]
                fw_major = (fw_val >> 8) & 0xFF
                fw_minor = fw_val & 0xFF
                hw_major = (hw_val >> 8) & 0xFF
                hw_minor = hw_val & 0xFF
                # Decodificar vendor/product preferentemente desde identidad extendida (hasta 8 bytes)
                v_val = hr[0]
                p_val = hr[1]
                v_str = None
                p_str = None
                if 'r_id' in locals() and not getattr(r_id, "isError", lambda: True)():
                    rid = r_id.registers or []
                    def _to_bytes(words):
                        out = bytearray()
                        for w in words:
                            out.append((w >> 8) & 0xFF)
                            out.append(w & 0xFF)
                        return bytes(out)
                    if len(rid) >= 10:
                        vlen = rid[0] & 0xFF
                        vbytes = _to_bytes(rid[1:5])
                        v_str = ''.join(chr(b) for b in vbytes[:vlen] if 32 <= b <= 126)
                        plen = rid[5] & 0xFF
                        pbytes = _to_bytes(rid[6:10])
                        p_str = ''.join(chr(b) for b in pbytes[:plen] if 32 <= b <= 126)
                # Alias extendido (hasta 64 bytes)
                alias_str = None
                if 'r_alias_len' in locals() and not getattr(r_alias_len, "isError", lambda: True)():
                    alen = (r_alias_len.registers or [0])[0] & 0xFFFF
                    if alen > 64:
                        alen = 64
                    if alen == 0:
                        # Si la longitud es 0, el firmware expone fallback "default" internamente; replicar aquí por claridad
                        alias_str = 'default'
                    elif 'r_alias' in locals() and r_alias is not None and not getattr(r_alias, "isError", lambda: True)():
                        ra = r_alias.registers or []
                        def _to_bytes(words):
                            out = bytearray()
                            for w in words:
                                out.append((w >> 8) & 0xFF)
                                out.append(w & 0xFF)
                            return bytes(out)
                        abytes = _to_bytes(ra)
                        alias_str = ''.join(chr(b) for b in abytes[:alen] if 32 <= b <= 126)
                # Fallback: 2 caracteres ASCII desde los words antiguos
                if not v_str:
                    msb = (v_val >> 8) & 0xFF
                    lsb = v_val & 0xFF
                    if 32 <= msb <= 126 and 32 <= lsb <= 126:
                        v_str = chr(msb) + chr(lsb)
                if not p_str:
                    msb = (p_val >> 8) & 0xFF
                    lsb = p_val & 0xFF
                    if 32 <= msb <= 126 and 32 <= lsb <= 126:
                        p_str = chr(msb) + chr(lsb)

                state["holding"] = {
                    "vendor": v_val, "product": p_val,
                    "vendor_str": v_str, "product_str": p_str,
                    "hw": hw_val, "fw": fw_val,
                    "hw_str": f"{hw_major}.{hw_minor}",
                    "fw_str": f"{fw_major}.{fw_minor}",
                    "alias_str": alias_str,
                    "unit_echo": hr[4], "caps": hr[5],
                    "uptime_s": to_s32(hr[6], hr[7]),
                    "status": hr[8], "errors": hr[9],
                }
                # Opcional: alinear el unit usado por los endpoints con el UnitID real del dispositivo
                if AUTO_ALIGN_UNIT:
                    try:
                        state["unit"] = int(hr[4])
                    except Exception:
                        pass
                state["poll_enabled"] = poll_enabled
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
    # Sincroniza flag del poller en el snapshot
    state["poll_enabled"] = poll_enabled
    return jsonify(state)  # Flask convierte dict -> JSON y añade cabeceras adecuadas

@app.route("/set_unit", methods=["POST"])
def set_unit():
    """Cambia dinámicamente el UNIT_ID usado por el Edge.
    Body: { "unit": <1..247> }
    Actualiza state["unit"] para que el poller y comandos usen la nueva unidad.
    """
    try:
        data = request.get_json(force=True)
        unit = int(data.get("unit", state["unit"]))
        if not (1 <= unit <= 247):
            return jsonify(ok=False, err="unit debe estar entre 1 y 247"), 400
        state["unit"] = unit
        log_event("set_unit", unit=unit)
        return jsonify(ok=True, unit=unit)
    except Exception as e:
        return jsonify(ok=False, err=str(e)), 500

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
        # Si había un temporizador pendiente, cancelarlo al forzar estado
        global pause_timer
        with pause_lock:
            if pause_timer is not None:
                try:
                    pause_timer.cancel()
                except Exception:
                    pass
                pause_timer = None
        log_event("poll_enabled", value=poll_enabled)
        return jsonify(ok=True, enabled=poll_enabled)
    except Exception as e:
        return jsonify(ok=False, err=str(e)), 500

def _resume_poll():
    global poll_enabled, pause_timer
    with pause_lock:
        poll_enabled = True
        pause_timer = None
        log_event("poll_enabled", value=poll_enabled)

@app.route("/diag/pause", methods=["POST"])
def diag_poll_pause():
    """Pausa el sondeo automáticamente durante N segundos y luego lo reanuda.
    Body: { seconds: <n> } (por defecto 10, rango 1..60)
    """
    try:
        data = request.get_json(force=True)
        seconds = int(data.get("seconds", 10))
        if seconds < 1:
            seconds = 1
        if seconds > 60:
            seconds = 60
        global poll_enabled, pause_timer
        with pause_lock:
            poll_enabled = False
            # cancelar pausa previa si había
            if pause_timer is not None:
                try:
                    pause_timer.cancel()
                except Exception:
                    pass
                pause_timer = None
            # programar reanudación
            pause_timer = threading.Timer(seconds, _resume_poll)
            pause_timer.daemon = True
            pause_timer.start()
        state["poll_enabled"] = poll_enabled
        log_event("poll_pause", seconds=seconds)
        return jsonify(ok=True, paused=True, resume_in=seconds)
    except Exception as e:
        return jsonify(ok=False, err=str(e)), 500

@app.route("/diag/read", methods=["POST"])
def diag_read():
    """Lee registros Modbus de forma ad-hoc para diagnóstico.
    Body JSON: { kind: "hr"|"ir", addr: <hex|dec>, count: <n>, unit?: <id> }
    """
    try:
        data = request.get_json(force=True)
        kind = str(data.get("kind", "hr")).lower()
        addr = int(str(data.get("addr")), 0)
        count = int(data.get("count", 1))
        unit = int(data.get("unit", state["unit"]))
        if count <= 0 or count > 32:
            return jsonify(ok=False, err="count_out_of_range"), 400
        with modbus_exclusive(timeout=2.5):
            if kind == "hr":
                log_event("diag_read_hr:req", unit=unit, addr=addr, count=count)
                res = cli.read_holding_registers(addr, count, unit=unit)
            else:
                log_event("diag_read_ir:req", unit=unit, addr=addr, count=count)
                res = cli.read_input_registers(addr, count, unit=unit)
        if getattr(res, "isError", lambda: True)():
            return jsonify(ok=False, err=str(res), exception_code=getattr(res, "exception_code", None)), 400
        regs = getattr(res, "registers", None)
        return jsonify(ok=True, registers=regs)
    except Exception as e:
        return jsonify(ok=False, err=str(e)), 500

@app.route("/diag/scan", methods=["POST"]) 
def diag_scan():
    """Escanea un rango de Unit IDs leyendo un registro sencillo (HR_INFO_ID_UNIDAD) y opcionalmente 0x11.
    Body: { start: <int>, end: <int>, includeInfo?: <bool> }
    """
    try:
        data = request.get_json(force=True)
        start = int(data.get("start", 1))
        end = int(data.get("end", 16))
        include_info = bool(data.get("includeInfo", False))
        if start < 1:
            start = 1
        if end > 247:
            end = 247
        if end < start:
            return jsonify(ok=False, err="range_invalid"), 400
        found = []
        with modbus_exclusive(timeout=1.5):
            for u in range(start, end+1):
                try:
                    log_event("scan:req", unit=u)
                    r = cli.read_holding_registers(HR["DEV_UNIT_ID"], 1, unit=u)
                    if getattr(r, "isError", lambda: True)():
                        continue
                    entry = {"unit": u, "dev_unit_id": (r.registers or [None])[0]}
                    if include_info:
                        try:
                            if hasattr(cli, "report_slave_id"):
                                res = cli.report_slave_id(unit=u)
                            else:
                                RequestCls = _get_report_slave_id_request_class()
                                if RequestCls and hasattr(cli, "execute"):
                                    try:
                                        res = cli.execute(RequestCls(unit=u), unit=u)
                                    except TypeError:
                                        req = RequestCls()
                                        setattr(req, "unit_id", u)
                                        try:
                                            res = cli.execute(req, unit=u)
                                        except TypeError:
                                            res = cli.execute(req)
                                else:
                                    res = None
                            if res and not getattr(res, "isError", lambda: True)():
                                payload = None
                                for attr in ("information", "data", "message"):
                                    val = getattr(res, attr, None)
                                    if val is not None:
                                        payload = val
                                        break
                                if isinstance(payload, list):
                                    payload = bytes(payload)
                                txt = None
                                sid = None
                                if isinstance(payload, (bytes, bytearray)) and len(payload) >= 3:
                                    if payload[0] == (len(payload)-1):
                                        sid = payload[1]
                                        txt = bytes(payload[3:]).decode("ascii", errors="ignore")
                                    else:
                                        sid = payload[0]
                                        txt = bytes(payload[2:]).decode("ascii", errors="ignore")
                                entry["slaveId"] = sid
                                entry["text"] = txt
                        except Exception:
                            pass
                    found.append(entry)
                except Exception:
                    continue
        return jsonify(ok=True, results=found)
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
            with modbus_exclusive(timeout=2.0):
                log_event("report_slave_id:req", unit=unit)
                res = cli.report_slave_id(unit=unit)
        else:
            # Intentar vía execute() con petición explícita
            RequestCls = _get_report_slave_id_request_class()
            if RequestCls is None or not hasattr(cli, "execute"):
                return jsonify(ok=False, err="ReportSlaveId no soportado por pymodbus"), 400
            with modbus_exclusive(timeout=2.0):
                log_event("report_slave_id:req-exec", unit=unit)
                try:
                    res = cli.execute(RequestCls(unit=unit), unit=unit)
                except TypeError:
                    # algunos constructores no aceptan unit; establecer atributo y pasar kwarg si posible
                    try:
                        req = RequestCls()
                        try:
                            setattr(req, "unit_id", unit)
                        except Exception:
                            pass
                        try:
                            res = cli.execute(req, unit=unit)
                        except TypeError:
                            res = cli.execute(req)
                    except Exception as ex:
                        return jsonify(ok=False, err=f"ReportSlaveId exec err: {ex}"), 500

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
        if payload is None:
            try:
                payload = res.encode()
            except Exception:
                payload = None
        if isinstance(payload, (bytes, bytearray)) and len(payload) >= 3:
            # Algunos backends incluyen el byteCount al inicio del payload (Modbus PDU);
            # otros exponen directamente [slaveId, runIndicator, ascii...].
            # Detectar la variante por longitud: si payload[0] == len(payload)-1, es byteCount.
            try:
                if payload[0] == (len(payload) - 1):
                    slave_id = payload[1]
                    running = (payload[2] == 0xFF)
                    ascii_info = bytes(payload[3:]).decode("ascii", errors="ignore")
                else:
                    slave_id = payload[0]
                    running = (payload[1] == 0xFF)
                    ascii_info = bytes(payload[2:]).decode("ascii", errors="ignore")
            except Exception:
                ascii_info = None

        state["unit"] = unit
        # Si se pudo parsear el texto, extraer FW/HW completos y actualizar resumen
        try:
            if isinstance(ascii_info, str):
                import re
                mFW = re.search(r"v(\d+)\.(\d+)\.(\d+)", ascii_info)
                mHW = re.search(r"HW(\d+)\.(\d+)\.(\d+)", ascii_info)
                if mFW:
                    state.setdefault("holding", {})["fw_str"] = f"{mFW.group(1)}.{mFW.group(2)}.{mFW.group(3)}"
                if mHW:
                    state.setdefault("holding", {})["hw_str"] = f"{mHW.group(1)}.{mHW.group(2)}.{mHW.group(3)}"
        except Exception:
            pass
        log_event("report_slave_id:ok", slaveId=slave_id, running=running, text=ascii_info)
        # Guardar último texto para que la UI lo vea vía /state si quiere
        state.setdefault("holding", {})["last_ident_text"] = ascii_info
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
            with modbus_exclusive(timeout=2.0):
                log_event("identify_0x41:req", unit=unit)
                res = cli.execute(req, unit=unit)
        except TypeError:
            # Fallback: establecer atributo unit_id en la request y ejecutar sin kwarg
            try:
                setattr(req, "unit_id", unit)
            except Exception:
                pass
            with modbus_exclusive(timeout=2.0):
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
        if payload is None:
            # Fallback: intentar serializar el response a bytes
            try:
                payload = res.encode()
            except Exception:
                payload = None

        slave_id = None
        running = None
        ascii_info = None
        if isinstance(payload, (bytes, bytearray)) and len(payload) >= 3:
            try:
                if payload[0] == (len(payload) - 1):
                    slave_id = payload[1]
                    running = (payload[2] == 0xFF)
                    ascii_info = bytes(payload[3:]).decode("ascii", errors="ignore")
                else:
                    slave_id = payload[0]
                    running = (payload[1] == 0xFF)
                    ascii_info = bytes(payload[2:]).decode("ascii", errors="ignore")
            except Exception:
                ascii_info = None

        state["unit"] = unit
        # Actualiza resumen con FW/HW completos si están en el texto
        try:
            if isinstance(ascii_info, str):
                import re
                mFW = re.search(r"v(\d+)\.(\d+)\.(\d+)", ascii_info)
                mHW = re.search(r"HW(\d+)\.(\d+)\.(\d+)", ascii_info)
                if mFW:
                    state.setdefault("holding", {})["fw_str"] = f"{mFW.group(1)}.{mFW.group(2)}.{mFW.group(3)}"
                if mHW:
                    state.setdefault("holding", {})["hw_str"] = f"{mHW.group(1)}.{mHW.group(2)}.{mHW.group(3)}"
        except Exception:
            pass
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
        with modbus_exclusive(timeout=2.0):
            # Evitar reintentos que causen escrituras duplicadas
            prev_retries = getattr(cli, "retries", None)
            prev_retry_empty = getattr(cli, "retry_on_empty", None)
            try:
                try:
                    cli.retries = 0
                except Exception:
                    pass
                try:
                    cli.retry_on_empty = False
                except Exception:
                    pass
                log_event("write_single:req", unit=unit, addr=addr, value=seconds)
                res = cli.write_register(addr, seconds, unit=unit)
            finally:
                if prev_retries is not None:
                    try:
                        cli.retries = prev_retries
                    except Exception:
                        pass
                if prev_retry_empty is not None:
                    try:
                        cli.retry_on_empty = prev_retry_empty
                    except Exception:
                        pass
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

@app.route("/alias", methods=["POST"])
def set_alias():
    """Escribe el alias del dispositivo usando 0x10 (Write Multiple Registers).
    Request JSON: { unit: <id>, alias: <string> }
    Estructura: [ALIAS_LEN, palabras de alias empaquetadas 2B/reg]
    """
    try:
        data = request.get_json(force=True)
        unit = int(data.get("unit", state["unit"]))
        alias = str(data.get("alias", "")).strip()
        if len(alias) > 64:
            alias = alias[:64]
        # Construir valores: primer word = longitud, luego 32 words con bytes
        values = [len(alias)]
        # Empaquetar en big-endian (MSB,LSB)
        for i in range(0, 64, 2):
            b0 = ord(alias[i]) if i < len(alias) else 0
            b1 = ord(alias[i+1]) if (i+1) < len(alias) else 0
            word = ((b0 & 0xFF) << 8) | (b1 & 0xFF)
            values.append(word)
        # Enviar 33 registros desde HR_ID_ALIAS_LEN (0x0030)
        start = 0x0030
        with modbus_exclusive(timeout=2.5):
            prev_retries = getattr(cli, "retries", None)
            prev_retry_empty = getattr(cli, "retry_on_empty", None)
            try:
                try:
                    cli.retries = 0
                except Exception:
                    pass
                try:
                    cli.retry_on_empty = False
                except Exception:
                    pass
                log_event("write_multiple:req", unit=unit, start=start, count=len(values))
                res = cli.write_registers(start, values, unit=unit)
            finally:
                if prev_retries is not None:
                    try:
                        cli.retries = prev_retries
                    except Exception:
                        pass
                if prev_retry_empty is not None:
                    try:
                        cli.retry_on_empty = prev_retry_empty
                    except Exception:
                        pass
        if getattr(res, "isError", lambda: True)():
            err = str(res)
            code = getattr(res, "exception_code", None)
            log_event("write_multiple:err", err=err, exception_code=code)
            return jsonify(ok=False, err=err, exception_code=code), 400
        # Refrescar alias localmente para feedback inmediato
        state.setdefault("holding", {})["alias_str"] = alias
        state["unit"] = unit
        log_event("write_multiple:ok")
        return jsonify(ok=True)
    except Exception as e:
        return jsonify(ok=False, err=str(e)), 500

# -----------------------------
# Main
# -----------------------------
if __name__ == "__main__":
    # Arranca el sondeo automático por defecto
    poll_enabled = True
    state["poll_enabled"] = True
    t = threading.Thread(target=poller, daemon=True)
    t.start()
    log_event("poll_enabled", value=True)
    # Servidor HTTP accesible en http://HOST:PORT_HTTP
    app.run(host=HOST, port=PORT_HTTP)
