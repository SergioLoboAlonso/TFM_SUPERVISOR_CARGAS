// -----------------------------------------------------------------------------
// <Archivo> — MODBUS Registers
// Proyecto: TFM Supervisor de Cargas (RS-485 + Modbus RTU)
// Autor: Sergio Lobo
// Notas: Cumple norma Modbus RTU. (CRC16 0xA001; broadcast sin respuesta).
// -----------------------------------------------------------------------------

// MAPA MODBUS (constantes y enums) — colocar aquí más adelante.
// - BASE_DATA, BASE_IDENTITY, BASE_PROV, BASE_DISCOVERY, BASE_CLAIM, BASE_IDENT_VIZ
// - STATUS_OK, DISC_*, CLAIM_*, IDENT_*
// - Declaraciones (extern) de variables de estado y prototipos:
//   void initStatic();
//   void updateMockMeasurements();
// -----------------------------------------------------------------------------
// registers.h — Contrato del mapa Modbus RTU (sin lógica)
// Proyecto: TFM Supervisor de Cargas (RS-485 + Modbus RTU)
// Autor: Sergio Lobo
// Notas:
//  - Direcciones en palabras Modbus (16 bits). Endianness: MSB→LSB en cada reg.
//  - RTU CRC16 (poly 0xA001, init 0xFFFF) y broadcast (addr=0) según norma.
//  - Este archivo declara estados/constantes y variables compartidas (extern).
// -----------------------------------------------------------------------------
#pragma once
#include <Arduino.h>

namespace Registers {

// -----------------------------------------------------------------------------
// 1) Direcciones base de bancos
// -----------------------------------------------------------------------------
static const uint16_t BASE_DATA        = 0x0000; // Medidas/estado instantáneo (Input/Holding)
static const uint16_t BASE_IDENTITY    = 0x0100; // Identidad y metadatos (Input/Holding)
static const uint16_t BASE_PROV        = 0x0400; // Provisión (Holding: write)
static const uint16_t BASE_DISCOVERY   = 0x0420; // Descubrimiento/estado (Input/Holding)
static const uint16_t BASE_CLAIM       = 0x0430; // Claim/ack de arranque (Holding)
static const uint16_t BASE_IDENT_VIZ   = 0x0440; // Identificación visual (Blink LED) (Holding)

// -----------------------------------------------------------------------------
// 2) Offsets (reg = base + offset). Mantener inmutables tras publicar una versión
// -----------------------------------------------------------------------------

// 2.1 DATA (0x0000) — Datos de telemetría expuestos por 0x04 (y espejo 0x03)
enum : uint16_t {
  REG_ANGLE_X = BASE_DATA + 0,   // int16  décimas de grado
  REG_ANGLE_Y = BASE_DATA + 1,   // int16  décimas de grado
  REG_STATUS  = BASE_DATA + 2,   // uint16 flags de estado
  REG_VIN_mV  = BASE_DATA + 3    // uint16 milivoltios
};

// 2.2 IDENTITY (0x0100) — Identidad persistente (ASCII en 2B/registro)
enum : uint16_t {
  REG_ID_VENDOR    = BASE_IDENTITY + 0,   // uint16 x8  (16B ASCII)
  REG_ID_MODEL     = BASE_IDENTITY + 8,   // uint16 x8  (16B ASCII)
  REG_ID_HW_REV    = BASE_IDENTITY + 16,  // uint16
  REG_ID_FW_REV    = BASE_IDENTITY + 17,  // uint16
  REG_ID_SERIAL_H  = BASE_IDENTITY + 18,  // uint16 (serial alto; MVP 32-bit total)
  REG_ID_SERIAL_L  = BASE_IDENTITY + 19,  // uint16 (serial bajo)
  REG_ID_ALIAS_LEN = BASE_IDENTITY + 20,  // uint16 (0..64)
  REG_ID_ALIAS0    = BASE_IDENTITY + 21   // uint16 x32 (64B ASCII)
};

// 2.3 PROVISION (0x0400) — Escrituras del Edge (aplican en caliente y persisten)
enum : uint16_t {
  REG_PROV_UNITID     = BASE_PROV + 0,    // WO uint16: nueva UnitID (1..247) → hot-apply + EEPROM
  REG_PROV_STATUS     = BASE_PROV + 1,    // RO uint16: 0=idle,2=ok,3=err_token,4=err_conflict,5=locked
  REG_PROV_TOKEN      = BASE_PROV + 2,    // WO uint16: opcional (no obligatorio en MVP)
  // Alias buffer a escribir (tras PROV_ALIAS_LEN):
  REG_PROV_ALIAS_LEN  = BASE_PROV + 8,    // RW uint16: longitud alias a persistir (0..64)
  REG_PROV_ALIAS0     = BASE_PROV + 9     // WO uint16 x32: alias ASCII (64B máx.)
};

// 2.4 DISCOVERY/STATE (0x0420)
enum : uint16_t {
  REG_DISCOVERY_CTRL  = BASE_DISCOVERY + 0, // RW uint16: 0=idle,1=START,2=STOP (permitir broadcast)
  REG_DISCOVERY_STATE = BASE_DISCOVERY + 1, // RO uint16: 0=idle,1=discovery,2=assigned
  REG_UNITID_ACTIVE   = BASE_DISCOVERY + 2, // RO uint16: UnitID actual en uso
  REG_UNITID_STORED   = BASE_DISCOVERY + 3  // RO uint16: UnitID persistida en EEPROM (0 si none)
};

// 2.5 CLAIM (0x0430)
enum : uint16_t {
  REG_CLAIM_STATUS = BASE_CLAIM + 0, // RO uint16: 0=idle,1=awaiting_ack,2=ack_ok,3=denied
  REG_CLAIM_ACK    = BASE_CLAIM + 1  // WO uint16: escribir 1 ⇒ pasa a ack_ok
};

// 2.6 IDENT VISUAL (Blink LED) (0x0440)
enum : uint16_t {
  REG_IDENT_CTRL      = BASE_IDENT_VIZ + 0, // WO uint16: 0=STOP,1=START,2=TOGGLE
  REG_IDENT_STATE     = BASE_IDENT_VIZ + 1, // RO uint16: 0=idle,1=active,2=unsupported
  REG_IDENT_TIMEOUT_S = BASE_IDENT_VIZ + 2, // RW uint16: segundos de actividad (p.ej. 60)
  REG_IDENT_PATTERN   = BASE_IDENT_VIZ + 3, // RW uint16: 0=default,1=doble1Hz,2=triple0.5Hz,3=ráfagas5Hz
  REG_IDENT_LED_MASK  = BASE_IDENT_VIZ + 4  // RW uint16: máscara (si hubiera múltiples LEDs)
};

// -----------------------------------------------------------------------------
// 3) Constantes y enums de estado (documentación compacta)
// -----------------------------------------------------------------------------

// STATUS bits (REG_STATUS): define solo los usados en MVP
enum : uint16_t {
  STATUS_OK        = 0x0001, // bit0=OK (equipo en servicio)
  // Reservas futuras: 0x0002 IMU_FAIL, 0x0004 OVERVOLT, etc.
};

// DISCOVERY_STATE
enum : uint16_t {
  DISC_IDLE     = 0,
  DISC_ACTIVE   = 1, // en ventana de discovery tras broadcast START
  DISC_ASSIGNED = 2  // con UnitID asignada/operativa
};

// CLAIM_STATUS
enum : uint16_t {
  CLAIM_IDLE   = 0,
  CLAIM_AWAIT  = 1, // arranque con UNITID_stored; espera ACK del Edge
  CLAIM_ACK_OK = 2,
  CLAIM_DENIED = 3
};

// IDENT control / state
enum : uint16_t {
  IDENT_STOP  = 0,
  IDENT_START = 1,
  IDENT_TOGGLE= 2
};
enum : uint16_t {
  IDENT_STATE_IDLE = 0,
  IDENT_STATE_ACTIVE = 1,
  IDENT_STATE_UNSUP = 2
};

// -----------------------------------------------------------------------------
// 4) Variables compartidas (definidas en un .cpp, aquí solo se declaran)
// -----------------------------------------------------------------------------

// 4.1 Medidas / estado
extern volatile int16_t  g_angleX_ddeg; // décimas de grado
extern volatile int16_t  g_angleY_ddeg; // décimas de grado
extern volatile uint16_t g_status;      // STATUS bits
extern volatile uint16_t g_vin_mV;      // milivoltios

// 4.2 Identidad
extern uint16_t g_idHwRev;
extern uint16_t g_idFwRev;
extern uint32_t g_idSerial;             // MVP 32-bit (ampliable a 64b si se desea)
extern char     g_alias[65];            // alias ASCII (null-terminated)
extern uint16_t g_aliasLen;             // 0..64

// 4.3 Provisión / descubrimiento / claim
extern uint16_t g_provStatus;           // REG_PROV_STATUS
extern uint16_t g_unitIdActive;         // REG_UNITID_ACTIVE
extern uint16_t g_unitIdStored;         // REG_UNITID_STORED
extern uint16_t g_discoveryState;       // REG_DISCOVERY_STATE
extern uint16_t g_claimStatus;          // REG_CLAIM_STATUS

// 4.4 Identificación visual
extern uint16_t g_identState;           // REG_IDENT_STATE
extern uint16_t g_identTimeoutS;        // REG_IDENT_TIMEOUT_S
extern uint16_t g_identPattern;         // REG_IDENT_PATTERN

// -----------------------------------------------------------------------------
// 5) API mínima de alto nivel (implementación fuera de este header)
// -----------------------------------------------------------------------------

// Inicializa campos estáticos de identidad (vendor/model/hw/fw por defecto).
void initStatic();

// Actualiza medidas simuladas (ejecútalo cada ~50 ms si aún no hay sensores reales).
void updateMockMeasurements();

} // namespace Registers