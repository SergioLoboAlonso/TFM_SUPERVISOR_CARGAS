"""
edge_v2.py — Edge Modbus RTU con protocolo de comunicación optimizado

Mejoras clave:
- Sistema de prioridades para lecturas (críticas vs. info)
- Pausa inter-frame adecuada (evita saturación del bus RS-485)
- Gestión robusta de timeouts y errores
- Identificación y registro simplificados
"""
import os
import time
import threading
import glob
import logging
from collections import deque

from flask import Flask, jsonify, render_template, request
from dotenv import load_dotenv
from pymodbus.client import ModbusSerialClient

# Funciones Modbus custom (0x11, 0x41)
from modbus_custom import register_custom_functions, report_slave_id, identify_blink

# ========== CONFIGURACIÓN ==========
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s: %(message)s'
)
log = logging.getLogger("edge_v2")

# Detección de puerto serie
def detect_port():
    cand = glob.glob("/dev/tty.usb*") + glob.glob("/dev/ttyUSB*")
    return cand[0] if cand else ("/dev/ttyUSB0" if os.name != "nt" else "COM3")

PORT = os.getenv("MODBUS_PORT", detect_port())
BAUD = int(os.getenv("MODBUS_BAUD", "115200"))
HOST = os.getenv("HOST", "0.0.0.0")
PORT_HTTP = int(os.getenv("PORT", "8080"))

# Tiempos críticos para RS-485
INTER_FRAME_DELAY_MS = 50   # Pausa entre frames consecutivos (evita colisiones)
POLL_CYCLE_MS = 500          # Ciclo completo de polling

# Mapa de registros
HR = {
    "DEV_VENDOR_ID": 0x0000, "DEV_PRODUCT_ID": 0x0001,
    "DEV_HW_VERSION": 0x0002, "DEV_FW_VERSION": 0x0003,
    "DEV_UNIT_ID": 0x0004, "DEV_CAPS": 0x0005,
    "DEV_UPTIME_LO": 0x0006, "DEV_UPTIME_HI": 0x0007,
    "DEV_STATUS": 0x0008, "DEV_ERRORS": 0x0009,
    "CMD_IDENT_SECS": 0x0013,
    "VENDOR_LEN": 0x0026, "VENDOR0": 0x0027,
    "PRODUCT_LEN": 0x002B, "PRODUCT0": 0x002C,
    "ALIAS_LEN": 0x0030, "ALIAS0": 0x0031,
}
IR = {
    "ANGLE_X": 0x0000, "ANGLE_Y": 0x0001, "TEMP": 0x0002,
    "ACC_X": 0x0003, "ACC_Y": 0x0004, "ACC_Z": 0x0005,
    "GYR_X": 0x0006, "GYR_Y": 0x0007, "GYR_Z": 0x0008,
    "SAMPLE_LO": 0x0009, "SAMPLE_HI": 0x000A, "FLAGS": 0x000B,
}

# ========== ESTADO GLOBAL ==========
state = {
    "unit": 1,  # UNIT_ID dinámico
    "port": PORT,
    "baud": BAUD,
    "connected": False,
    "last_error": None,
    "telemetry": {},     # Datos críticos (ángulos, sensores)
    "device_info": {},   # Info del dispositivo (vendor, FW, HW)
    "poll_enabled": True,
}

diag_log = deque(maxlen=200)
def log_event(kind, **fields):
    evt = {"ts": time.time(), "kind": kind}
    evt.update(fields)
    diag_log.append(evt)

# ========== CLIENTE MODBUS ==========
cli = ModbusSerialClient(
    port=PORT,
    baudrate=BAUD,
    parity="N",
    stopbits=1,
    bytesize=8,
    timeout=2.0,  # Timeout más largo para RS-485 lento
    retries=1,
)
cli_lock = threading.Lock()

# Registrar funciones custom 0x11 y 0x41 en el decoder
register_custom_functions(cli)

def safe_read_hr(unit, start, count):
    """Lectura segura de Holding Registers con logging"""
    try:
        log_event("read_hr:req", slave=unit, start=start, count=count)
        resp = cli.read_holding_registers(start, count, slave=unit)
        if resp.isError():
            log_event("read_hr:err", slave=unit, error=str(resp))
            return None
        log_event("read_hr:ok", slave=unit, count=len(resp.registers))
        return resp.registers
    except Exception as e:
        log_event("read_hr:exc", slave=unit, error=str(e))
        return None

def safe_read_ir(unit, start, count):
    """Lectura segura de Input Registers con logging"""
    try:
        log_event("read_ir:req", slave=unit, start=start, count=count)
        resp = cli.read_input_registers(start, count, slave=unit)
        if resp.isError():
            log_event("read_ir:err", slave=unit, error=str(resp))
            return None
        log_event("read_ir:ok", slave=unit, count=len(resp.registers))
        return resp.registers
    except Exception as e:
        log_event("read_ir:exc", slave=unit, error=str(e))
        return None

def safe_write_hr(unit, reg, value):
    """Escritura segura de Holding Register"""
    try:
        log_event("write_hr:req", slave=unit, reg=reg, value=value)
        resp = cli.write_register(reg, value, slave=unit)
        if resp.isError():
            log_event("write_hr:err", slave=unit, error=str(resp))
            return False
        log_event("write_hr:ok", slave=unit)
        return True
    except Exception as e:
        log_event("write_hr:exc", slave=unit, error=str(e))
        return False

def inter_frame_delay():
    """Pausa entre frames para evitar saturación del bus"""
    time.sleep(INTER_FRAME_DELAY_MS / 1000.0)

# ========== POLLER CON PRIORIDADES ==========
poll_enabled = True

def poller_worker():
    """
    Hilo de polling optimizado con sistema de prioridades:
    - Ciclo 1: Telemetría crítica (ángulos, sensores)
    - Ciclo 2: Info básica del dispositivo
    - Ciclo 3: Info extendida (vendor, alias)
    """
    global state
    cycle = 0
    
    while True:
        try:
            if not poll_enabled:
                time.sleep(0.5)
                continue
            
            unit = state["unit"]
            
            # Conectar si es necesario
            with cli_lock:
                if not state["connected"]:
                    state["connected"] = cli.connect()
                    if not state["connected"]:
                        state["last_error"] = "connect_failed"
                        time.sleep(1)
                        continue
            
            # PRIORIDAD 1: Telemetría (siempre)
            with cli_lock:
                ir_data = safe_read_ir(unit, IR["ANGLE_X"], 12)
            
            if ir_data:
                state["telemetry"] = {
                    "angles_mdeg": {"x": ir_data[0], "y": ir_data[1]},
                    "temp_mC": ir_data[2],
                    "acc_mg": {"x": ir_data[3], "y": ir_data[4], "z": ir_data[5]},
                    "gyr_mdps": {"x": ir_data[6], "y": ir_data[7], "z": ir_data[8]},
                    "sample_count": (ir_data[9] | (ir_data[10] << 16)),
                    "flags": ir_data[11],
                }
                state["connected"] = True
                state["last_error"] = None
            else:
                state["connected"] = False
                state["last_error"] = "telemetry_read_failed"
            
            inter_frame_delay()
            
            # PRIORIDAD 2: Info básica del dispositivo (cada 3 ciclos)
            if cycle % 3 == 0:
                with cli_lock:
                    hr_info = safe_read_hr(unit, HR["DEV_VENDOR_ID"], 10)
                
                if hr_info:
                    state["device_info"]["vendor_id"] = hr_info[0]
                    state["device_info"]["product_id"] = hr_info[1]
                    state["device_info"]["hw_version"] = hr_info[2]
                    state["device_info"]["fw_version"] = hr_info[3]
                    state["device_info"]["unit_echo"] = hr_info[4]
                    state["device_info"]["caps"] = hr_info[5]
                    state["device_info"]["uptime_s"] = hr_info[6] | (hr_info[7] << 16)
                    state["device_info"]["status"] = hr_info[8]
                    state["device_info"]["errors"] = hr_info[9]
                
                inter_frame_delay()
            
            # PRIORIDAD 3: Info extendida (cada 10 ciclos)
            if cycle % 10 == 0:
                # Leer vendor string
                with cli_lock:
                    vendor_info = safe_read_hr(unit, HR["VENDOR_LEN"], 5)
                
                if vendor_info:
                    vlen = vendor_info[0] & 0xFF
                    if vlen > 0 and vlen <= 8:
                        vbytes = bytearray()
                        for w in vendor_info[1:5]:
                            vbytes.append((w >> 8) & 0xFF)
                            vbytes.append(w & 0xFF)
                        state["device_info"]["vendor_str"] = vbytes[:vlen].decode('ascii', errors='ignore')
                
                inter_frame_delay()
                
                # Leer product string
                with cli_lock:
                    product_info = safe_read_hr(unit, HR["PRODUCT_LEN"], 5)
                
                if product_info:
                    plen = product_info[0] & 0xFF
                    if plen > 0 and plen <= 8:
                        pbytes = bytearray()
                        for w in product_info[1:5]:
                            pbytes.append((w >> 8) & 0xFF)
                            pbytes.append(w & 0xFF)
                        state["device_info"]["product_str"] = pbytes[:plen].decode('ascii', errors='ignore')
                
                inter_frame_delay()
            
            cycle += 1
            time.sleep(POLL_CYCLE_MS / 1000.0)
            
        except Exception as e:
            log.error(f"Poller error: {e}")
            state["connected"] = False
            state["last_error"] = str(e)
            time.sleep(1)

# Iniciar poller
poller_thread = threading.Thread(target=poller_worker, daemon=True)
poller_thread.start()

# ========== FLASK APP ==========
app = Flask(__name__, template_folder="templates", static_folder="static")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/state")
def get_state():
    state["poll_enabled"] = poll_enabled
    return jsonify(state)

@app.route("/set_unit", methods=["POST"])
def set_unit():
    try:
        data = request.get_json(force=True)
        unit = int(data.get("unit", state["unit"]))
        if not (1 <= unit <= 247):
            return jsonify(ok=False, err="unit must be 1-247"), 400
        state["unit"] = unit
        log_event("set_unit", slave=unit)
        return jsonify(ok=True, slave=unit)
    except Exception as e:
        return jsonify(ok=False, err=str(e)), 500

@app.route("/identify", methods=["POST"])
def identify():
    """Comando 0x11 Report Slave ID - Función Modbus estándar"""
    try:
        data = request.get_json(force=True)
        unit = int(data.get("unit", state["unit"]))
        
        with cli_lock:
            log_event("identify:req", slave=unit, function=0x11)
            result = report_slave_id(cli, slave=unit)
            log_event("identify:ok", slave=unit, info=result['info'][:50])
        
        return jsonify(ok=True, **result)
                
    except Exception as e:
        log.error(f"Identify error: {e}")
        log_event("identify:err", error=str(e))
        return jsonify(ok=False, err=str(e)), 500

@app.route("/identify/trigger", methods=["POST"])
def identify_trigger():
    """Comando 0x41 propietario - Trigger LED + Info"""
    try:
        data = request.get_json(force=True)
        unit = int(data.get("unit", state["unit"]))
        
        with cli_lock:
            log_event("identify_trigger:req", slave=unit, function=0x41)
            result = identify_blink(cli, slave=unit)
            log_event("identify_trigger:ok", slave=unit, info=result['info'][:50])
        
        return jsonify(ok=True, **result)
                
    except Exception as e:
        log.error(f"Identify trigger error: {e}")
        log_event("identify_trigger:err", error=str(e))
        return jsonify(ok=False, err=str(e)), 500

@app.route("/identify/seconds", methods=["POST"])
def identify_seconds():
    """Escribe HR_CMD_IDENT_SECS para disparar Identify LED"""
    try:
        data = request.get_json(force=True)
        unit = int(data.get("unit", state["unit"]))
        seconds = int(data.get("seconds", 5))
        
        with cli_lock:
            ok = safe_write_hr(unit, HR["CMD_IDENT_SECS"], seconds)
        
        if ok:
            return jsonify(ok=True, seconds=seconds)
        else:
            return jsonify(ok=False, err="Write failed"), 400
            
    except Exception as e:
        return jsonify(ok=False, err=str(e)), 500

@app.route("/alias", methods=["POST"])
def write_alias():
    """Escribe alias (0x10 Write Multiple)"""
    try:
        data = request.get_json(force=True)
        unit = int(data.get("unit", state["unit"]))
        alias = str(data.get("alias", ""))[:64]
        
        # Codificar alias a words
        alen = len(alias)
        words = [alen]
        alias_bytes = alias.encode('ascii')
        for i in range(0, len(alias_bytes), 2):
            b1 = alias_bytes[i]
            b2 = alias_bytes[i+1] if i+1 < len(alias_bytes) else 0
            words.append((b1 << 8) | b2)
        
        with cli_lock:
            log_event("write_alias:req", slave=unit, alias=alias)
            resp = cli.write_registers(HR["ALIAS_LEN"], words, slave=unit)
            if resp.isError():
                return jsonify(ok=False, err=str(resp)), 400
        
        return jsonify(ok=True, alias=alias)
        
    except Exception as e:
        return jsonify(ok=False, err=str(e)), 500

@app.route("/diag/logs")
def diag_logs():
    return jsonify(list(diag_log))

@app.route("/diag/poll", methods=["POST"])
def diag_poll_toggle():
    global poll_enabled
    try:
        data = request.get_json(force=True)
        poll_enabled = bool(data.get("enable", True))
        return jsonify(ok=True, enabled=poll_enabled)
    except Exception as e:
        return jsonify(ok=False, err=str(e)), 500

if __name__ == "__main__":
    log.info(f"Starting Edge v2 on {HOST}:{PORT_HTTP}")
    log.info(f"Modbus: {PORT} @ {BAUD} baud")
    app.run(host=HOST, port=PORT_HTTP, debug=False)
