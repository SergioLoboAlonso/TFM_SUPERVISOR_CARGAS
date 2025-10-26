import os, time, threading, json
from flask import Flask, jsonify, render_template, request
from dotenv import load_dotenv
from pymodbus.client import ModbusSerialClient

load_dotenv()

PORT = os.getenv("MODBUS_PORT", "/dev/ttyUSB0")
BAUD = int(os.getenv("MODBUS_BAUD", "115200"))
UNIT = int(os.getenv("UNIT_ID", "1"))
POLL_MS = int(os.getenv("POLL_MS", "200"))
HOST = os.getenv("HOST", "0.0.0.0")
PORT_HTTP = int(os.getenv("PORT", "8080"))

HR = dict(DEV_VENDOR_ID=0x0000, DEV_PRODUCT_ID=0x0001, DEV_HW_VERSION=0x0002,
          DEV_FW_VERSION=0x0003, DEV_UNIT_ID=0x0004, DEV_CAPS=0x0005,
          DEV_UPTIME_LO=0x0006, DEV_UPTIME_HI=0x0007, DEV_STATUS=0x0008,
          DEV_ERRORS=0x0009, CMD_IDENT_SECS=0x0013)
IR = dict(ANGLE_X=0x0000, ANGLE_Y=0x0001, TEMP=0x0002,
          ACC_X=0x0003, ACC_Y=0x0004, ACC_Z=0x0005,
          GYR_X=0x0006, GYR_Y=0x0007, GYR_Z=0x0008,
          SAMPLE_LO=0x0009, SAMPLE_HI=0x000A, FLAGS=0x000B)

state = {
  "unit": UNIT, "port": PORT, "baud": BAUD,
  "connected": False, "last_error": None,
  "holding": {}, "input": {}
}

cli = ModbusSerialClient(method="rtu", port=PORT, baudrate=BAUD,
                         timeout=0.3, parity="N", stopbits=1, bytesize=8)

def to_s32(lo, hi): return (hi<<16) | lo

def poller():
  global cli, state
  while True:
    try:
      if not state["connected"]:
        state["connected"] = cli.connect()
        if not state["connected"]:
          state["last_error"] = "connect_failed"
          time.sleep(1); continue

      r1 = cli.read_input_registers(IR["ANGLE_X"], 12, slave=state["unit"])
      r2 = cli.read_holding_registers(HR["DEV_VENDOR_ID"], 10, slave=state["unit"])
      if not r1.isError():
        ir = r1.registers
        state["input"] = {
          "angles_mdeg": {"x": ir[0], "y": ir[1]},
          "temp_mC": ir[2],
          "acc_mg": {"x": ir[3], "y": ir[4], "z": ir[5]},
          "gyr_mdps": {"x": ir[6], "y": ir[7], "z": ir[8]},
          "sample_count": to_s32(ir[9], ir[10]),
          "flags": ir[11],
        }
      else:
        state["last_error"] = f"ir:{r1}"

      if not r2.isError():
        hr = r2.registers
        state["holding"] = {
          "vendor": hr[0], "product": hr[1],
          "hw": hr[2], "fw": hr[3],
          "unit_echo": hr[4], "caps": hr[5],
          "uptime_s": to_s32(hr[6], hr[7]),
          "status": hr[8], "errors": hr[9]
        }
      else:
        state["last_error"] = f"hr:{r2}"

    except Exception as e:
      state["connected"] = False
      state["last_error"] = str(e)
      try: cli.close()
      except: pass
      cli = ModbusSerialClient(method="rtu", port=PORT, baudrate=BAUD,
                               timeout=0.3, parity="N", stopbits=1, bytesize=8)
      time.sleep(1)
    time.sleep(POLL_MS/1000.0)

app = Flask(__name__, template_folder="templates", static_folder="static")

@app.route("/")
def idx(): return render_template("index.html")

@app.route("/state")
def get_state(): return jsonify(state)

@app.route("/identify", methods=["POST"])
def identify():
  try:
    data = request.get_json(force=True)
    unit = int(data.get("unit", state["unit"]))
    seconds = int(data.get("seconds", 0))
    res = cli.write_register(HR["CMD_IDENT_SECS"], seconds, slave=unit)
    if res.isError(): return jsonify(ok=False, err=str(res)), 400
    state["unit"] = unit
    return jsonify(ok=True)
  except Exception as e:
    return jsonify(ok=False, err=str(e)), 500

if __name__ == "__main__":
  t = threading.Thread(target=poller, daemon=True); t.start()
  app.run(host=HOST, port=PORT_HTTP)
