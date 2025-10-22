#!/usr/bin/env bash
set -euo pipefail

# -------------------------------
# TFM – Setup estructura PlatformIO
# -------------------------------

# 1) Árbol de firmware (PlatformIO)
mkdir -p firmware/{include,lib,src,test}

# 2) platformio.ini (solo si no existe)
if [ ! -f firmware/platformio.ini ]; then
  cat > firmware/platformio.ini <<'EOF'
[platformio]
default_envs = uno

[env]
framework = arduino
monitor_speed = 115200

[env:uno]
platform = atmelavr
board = uno

; Puedes duplicar el entorno para Nano:
; [env:nano]
; platform = atmelavr
; board = nanoatmega328new
EOF
  echo "Creado: firmware/platformio.ini"
else
  echo "Omitido: firmware/platformio.ini (ya existe)"
fi

# 3) Headers públicos (placeholders, sin lógica)
create_if_absent() {
  local path="$1"; shift
  local content="$*"
  if [ ! -f "$path" ]; then
    mkdir -p "$(dirname "$path")"
    printf "%s\n" "$content" > "$path"
    echo "Creado: $path"
  else
    echo "Omitido: $path (ya existe)"
  fi
}

HDR_HEADER='// -----------------------------------------------------------------------------
// <Archivo> — Placeholder (sin lógica)
// Proyecto: TFM Supervisor de Cargas (RS-485 + Modbus RTU)
// Autor: Sergio Lobo
// Notas: Cumple norma Modbus RTU (CRC16 0xA001; broadcast sin respuesta).
// -----------------------------------------------------------------------------'

create_if_absent "firmware/include/registers.h" \
"$HDR_HEADER
#pragma once
// MAPA MODBUS (constantes y enums) — colocar aquí más adelante.
// - BASE_DATA, BASE_IDENTITY, BASE_PROV, BASE_DISCOVERY, BASE_CLAIM, BASE_IDENT_VIZ
// - STATUS_OK, DISC_*, CLAIM_*, IDENT_*
// - Declaraciones (extern) de variables de estado y prototipos:
//   void initStatic();
//   void updateMockMeasurements();"

create_if_absent "firmware/include/config_pins.h" \
"$HDR_HEADER
#pragma once
// Pines de hardware (ajustar cuando implementemos):
// constexpr uint8_t PIN_DERE = 2;   // MAX485 RE+DE
// constexpr uint8_t PIN_LED  = 13;  // LED identificación
// Velocidad UART sugerida: 115200 8N1"

create_if_absent "firmware/include/firmware_version.h" \
"$HDR_HEADER
#pragma once
// #define FW_VERSION_MAJOR 1
// #define FW_VERSION_MINOR 0
// #define FW_VERSION_PATCH 0
// #define HW_REV 1
// #define FW_BUILD_DATE \"YYYY-MM-DD\""

# 4) main.cpp mínimo (compila vacío si algún día quieres probar; no incluye módulos)
create_if_absent "firmware/src/main.cpp" \
"$HDR_HEADER
#include <Arduino.h>
// Stub mínimo sin lógica (se rellenará más adelante)
void setup() {}
void loop()  {}"

# 5) Módulos internos — carpetas y archivos vacíos (sin contenido funcional)
for MOD in ModbusRTU EepromUtils BlinkIdent StateMachine utils; do
  mkdir -p "firmware/lib/$MOD/include" "firmware/lib/$MOD/src"
done

create_if_absent "firmware/lib/ModbusRTU/include/ModbusRTU.h" \
"$HDR_HEADER
#pragma once
// API prevista:
// class ModbusRTU { public: ModbusRTU(uint8_t pinDeRe); void process(); void setUnitId(uint8_t); static uint16_t crc16(const uint8_t*, size_t); };"

create_if_absent "firmware/lib/ModbusRTU/src/ModbusRTU.cpp" \
"$HDR_HEADER
// Implementación pendiente (parser RTU, funciones 0x03/0x04/0x06/0x10)."

create_if_absent "firmware/lib/EepromUtils/include/EepromUtils.h" \
"$HDR_HEADER
#pragma once
// API prevista:
// namespace EepromUtils {
//   void begin();
//   uint32_t readSerial(); void writeSerial(uint32_t);
//   uint16_t readUnitId(); void writeUnitId(uint16_t);
//   void readAlias(char* out, uint16_t& len);
//   void writeAlias(const char* in, uint16_t len);
// }"

create_if_absent "firmware/lib/EepromUtils/src/EepromUtils.cpp" \
"$HDR_HEADER
// Implementación pendiente (layout EEPROM, commit, límites)."

create_if_absent "firmware/lib/BlinkIdent/include/BlinkIdent.h" \
"$HDR_HEADER
#pragma once
// API prevista:
// class BlinkIdent { public: BlinkIdent(uint8_t pin); void begin(); void start(uint16_t pattern, uint16_t timeoutS); void stop(); void update(); };"

create_if_absent "firmware/lib/BlinkIdent/src/BlinkIdent.cpp" \
"$HDR_HEADER
// Implementación pendiente (parpadeo no bloqueante con millis())."

create_if_absent "firmware/lib/StateMachine/include/StateMachine.h" \
"$HDR_HEADER
#pragma once
// API prevista:
// class StateMachine { public: StateMachine(class ModbusRTU*, class BlinkIdent*); void begin(); void update(); };"

create_if_absent "firmware/lib/StateMachine/src/StateMachine.cpp" \
"$HDR_HEADER
// Implementación pendiente (INIT, PRECLAIM, DISCOVERY, OPERATIONAL)."

create_if_absent "firmware/lib/utils/include/crc16_utils.h" \
"$HDR_HEADER
#pragma once
// API prevista:
// uint16_t modbus_crc16(const uint8_t* data, size_t len);"

create_if_absent "firmware/lib/utils/src/crc16_utils.cpp" \
"$HDR_HEADER
// Implementación pendiente (CRC16 Modbus 0xA001)."

# 6) Test placeholder (opcional)
create_if_absent "firmware/test/test_registers.cpp" \
"$HDR_HEADER
// Pruebas (PlatformIO) — se añadirán cuando haya implementación."

echo "✔ Estructura PlatformIO preparada sin sobrescribir tus README."
