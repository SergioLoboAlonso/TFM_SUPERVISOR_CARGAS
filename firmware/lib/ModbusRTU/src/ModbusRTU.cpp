// -----------------------------------------------------------------------------
// ModbusRTU.cpp — Servidor Modbus RTU (AVR, UART + MAX485 puentado DE/RE)
//
// Funciones soportadas
// - 0x03 (Read Holding), 0x04 (Read Input), 0x06 (Write Single Holding)
// - Broadcast (unidad=0) permitido sólo para 0x06 y sin respuesta (según norma)
//
// Ensamblado de trama y delimitación
// - Se acumulan bytes recibidos en m_rxBuf y se toma la trama como completa cuando
//   hay silencio >= t3.5 caracteres (calculado a partir del baudrate).
// - El tiempo de 1 caracter se aproxima como 10 bits (8N1), por lo que
//   char_us ≈ 10e6/baud. De ahí t1.5 y t3.5.
//
// Validaciones implementadas
// - CRC16 verificado antes de procesar.
// - Longitud mínima de petición RTU (8 bytes: unit, func, startHi, startLo, cntHi, cntLo, crcLo, crcHi)
// - Rango de direcciones y número de palabras acotado por MAX_*.
// - Excepciones: función ilegal, dirección ilegal, valor ilegal.
// -----------------------------------------------------------------------------
#include "ModbusRTU.h"
#include "registersModbus.h"
#include "crc16_utils.h" // Unifica CRC usando utilidades comunes
#include "firmware_version.h" // Para componer la respuesta de Identify (0x11)

// ---------- Config mínimos ----------
#ifndef UNIT_ID
  #define UNIT_ID 1
#endif

// ---------- Excepciones ----------
enum : uint8_t {
  MB_EX_ILLEGAL_FUNCTION    = 0x01,
  MB_EX_ILLEGAL_DATA_ADDRESS= 0x02,
  MB_EX_ILLEGAL_DATA_VALUE  = 0x03,
  MB_EX_SERVER_DEVICE_FAIL  = 0x04
};

// (El CRC16 se calcula con modbus_crc16() de utils)
// ---------- Utilidades ----------
static inline uint16_t u16_be(const uint8_t* p){ return (uint16_t(p[0])<<8) | p[1]; }
static inline void     put_u16_be(uint8_t* p, uint16_t v){ p[0]=uint8_t(v>>8); p[1]=uint8_t(v&0xFF); }

void ModbusRTU::setTransmit(bool en){
  digitalWrite(m_derePin, en ? HIGH : LOW);
}

void ModbusRTU::clearRx(){
  m_rxLen = 0;
}

// ---------- Inicialización ----------
void ModbusRTU::begin(HardwareSerial& serial, uint32_t baud, uint8_t derePin){
  m_serial = &serial;
  m_derePin = derePin;

  pinMode(m_derePin, OUTPUT);
  setTransmit(false);                             // RX por defecto

  m_serial->begin(baud, SERIAL_8N1);

  // Tiempos RTU (en microsegundos)
  // 1 carácter ~ 10 bits -> 10/baud s -> (10e6/baud) us
  uint32_t char_us = (10000000UL / baud);
  // Tiempos Modbus (usar márgenes)
  t15_us = (char_us * 15) / 10;                  // ~1.5 char
  t35_us = (char_us * 35) / 10;                  // ~3.5 char

  lastByteUs = 0;
  clearRx();
  regs_init();
}

// ---------- TX con CRC ----------
void ModbusRTU::sendResponse(const uint8_t* p, uint8_t n){
  uint8_t buf[256];
  if(n > 252) return;                             // margen para CRC
  memcpy(buf, p, n);
  uint16_t crc = modbus_crc16(buf, n);           // CRC16 común (utils)
  buf[n++] = uint8_t(crc & 0xFF);                 // CRC L
  buf[n++] = uint8_t(crc >> 8);                   // CRC H

  setTransmit(true);
  m_serial->write(buf, n);
  m_serial->flush();                               // espera TX vacía
  // Pequeña guarda para asegurar que el transceptor RS‑485 completa el envío
  // antes de volver a modo recepción (ayuda en algunos MAX485 puentados DE/RE)
  if(t15_us > 0){
    delayMicroseconds(t15_us);
  }
  setTransmit(false);
}

// ---------- Excepción ----------
void ModbusRTU::sendException(uint8_t unit, uint8_t func, uint8_t ex){
  uint8_t pdu[3] = { unit, uint8_t(func | 0x80), ex };
  sendResponse(pdu, sizeof(pdu));
  regs_diag_inc(HR_DIAG_RX_EXCEPCIONES);
}

// ---------- Handlers ----------
void ModbusRTU::handleReadHolding(uint8_t unit, uint16_t start, uint16_t count, bool isInput){
  if(count==0) { sendException(unit, isInput?0x04:0x03, MB_EX_ILLEGAL_DATA_VALUE); return; }

  // Validación y lectura al buffer temporal
  uint16_t tmpCnt = count;
  if(tmpCnt > (isInput ? MAX_INPUT_READ : MAX_HOLDING_READ)){
    sendException(unit, isInput?0x04:0x03, MB_EX_ILLEGAL_DATA_VALUE); return;
  }

  uint16_t words[64];                             // suficiente para MAX_* = 32
  bool ok = isInput
    ? regs_read_input(start,  tmpCnt, words)
    : regs_read_holding(start,tmpCnt, words);

  if(!ok){ sendException(unit, isInput?0x04:0x03, MB_EX_ILLEGAL_DATA_ADDRESS); return; }

  // Construir respuesta: unit, func, byteCount, data...
  const uint8_t func = isInput ? 0x04 : 0x03;
  uint8_t resp[3 + 2*64];
  resp[0] = unit;
  resp[1] = func;
  resp[2] = uint8_t(tmpCnt*2);
  for(uint16_t i=0;i<tmpCnt;i++){
    put_u16_be(&resp[3 + 2*i], words[i]);
  }
  sendResponse(resp, uint8_t(3 + 2*tmpCnt));
}

void ModbusRTU::handleWriteSingle(uint8_t unit, uint16_t reg, uint16_t value, bool isBroadcast){
  bool ok = regs_write_holding(reg, value);
  if(isBroadcast){
    // No responder por norma en broadcast
    return;
  }
  if(!ok){ sendException(unit, 0x06, MB_EX_ILLEGAL_DATA_ADDRESS); return; }

  // Eco estándar de 0x06: misma PDU de petición
  uint8_t resp[6];
  resp[0] = unit;
  resp[1] = 0x06;
  put_u16_be(&resp[2], reg);
  put_u16_be(&resp[4], value);
  sendResponse(resp, sizeof(resp));
}

void ModbusRTU::handleWriteMultiple(uint8_t unit, uint16_t start, uint16_t count, const uint16_t* values, bool isBroadcast){
  bool ok = false;
  if(values && count>0){
    ok = regs_write_multi(start, count, values);
  }
  if(isBroadcast){
    // No responder por norma en broadcast
    return;
  }
  if(!ok){ sendException(unit, 0x10, MB_EX_ILLEGAL_DATA_ADDRESS); return; }
  // Respuesta estándar: eco de start y count
  uint8_t resp[6];
  resp[0] = unit;
  resp[1] = 0x10;
  put_u16_be(&resp[2], start);
  put_u16_be(&resp[4], count);
  sendResponse(resp, sizeof(resp));
}

// ---------- Parser de petición ----------
void ModbusRTU::handleRequest(const uint8_t* p, uint8_t n){
  // Mínimo absoluto para RTU: unit(1) + func(1) + CRC(2) = 4 bytes
  if(n < 4) return;
  // Validar CRC
  uint16_t rx_crc = uint16_t(p[n-2]) | (uint16_t(p[n-1])<<8);
  if(modbus_crc16(p, n-2) != rx_crc){            // Verificación CRC con utils
  regs_diag_inc(HR_DIAG_RX_CRC_ERROR);
    return;
  }

  const uint8_t unit = p[0];
  const uint8_t func = p[1];

  const bool isBroadcast = (unit == 0);
  if(!isBroadcast && unit != UNIT_ID){
    // No es para mí
    return;
  }

  // Validación mínima por función (algunas no llevan campo de dirección/contador)
  switch(func){
    case 0x03: { // Read Holding
      // unit, func, startHi, startLo, cntHi, cntLo, crcLo, crcHi
      if(n < 8){ sendException(unit, func, MB_EX_ILLEGAL_DATA_VALUE); return; }
      uint16_t start = u16_be(&p[2]);
      uint16_t count = u16_be(&p[4]);
      handleReadHolding(unit, start, count, /*isInput=*/false);
      break;
    }
    case 0x04: { // Read Input
      if(n < 8){ sendException(unit, func, MB_EX_ILLEGAL_DATA_VALUE); return; }
      uint16_t start = u16_be(&p[2]);
      uint16_t count = u16_be(&p[4]);
      handleReadHolding(unit, start, count, /*isInput=*/true);
      break;
    }
    case 0x06: { // Write Single Register
      if(n < 8){ sendException(unit, func, MB_EX_ILLEGAL_DATA_VALUE); return; }
      uint16_t reg   = u16_be(&p[2]);
      uint16_t value = u16_be(&p[4]);
      handleWriteSingle(unit, reg, value, isBroadcast);
      break;
    }
    case 0x10: { // Write Multiple Registers
      // unit, func, startHi, startLo, cntHi, cntLo, byteCount, data..., crcLo, crcHi
      if(n < 9){ sendException(unit, func, MB_EX_ILLEGAL_DATA_VALUE); return; }
      uint16_t start = u16_be(&p[2]);
      uint16_t count = u16_be(&p[4]);
      uint8_t  bc    = p[6];
      if(count==0 || bc != (uint8_t)(count*2) || n != (uint8_t)(9 + bc)){
        sendException(unit, func, MB_EX_ILLEGAL_DATA_VALUE); return;
      }
      // Convertir bytes big-endian a words
      uint16_t vals[64];
      if(count > 64){ sendException(unit, func, MB_EX_ILLEGAL_DATA_VALUE); return; }
      for(uint16_t i=0;i<count;i++){
        vals[i] = (uint16_t(p[7 + 2*i])<<8) | p[7 + 2*i + 1];
      }
      handleWriteMultiple(unit, start, count, vals, isBroadcast);
      break;
    }
    case 0x11: { // Report Slave ID (Identify)
      // Petición sin datos: unit, func, crcLo, crcHi
      if(n < 4){ sendException(unit, func, MB_EX_ILLEGAL_DATA_VALUE); return; }
      // No responder a broadcast (descubrimiento silencioso)
      if(isBroadcast) return;
      handleReportSlaveId(unit); // Sólo información; sin trigger
      break;
    }
    case 0x41: { // Proprietary Identify + Info
      // Petición sin datos: unit, func, crcLo, crcHi
      if(n < 4){ sendException(unit, func, MB_EX_ILLEGAL_DATA_VALUE); return; }
      // No responder a broadcast
      if(isBroadcast) return;
      handleIdentifyBlinkAndInfo(unit);
      break;
    }
    default:
      if(!isBroadcast) sendException(unit, func, MB_EX_ILLEGAL_FUNCTION);
      break;
  }
}

// ---------- Bucle de recepción ----------
// Estrategia: acumular bytes y delimitar por silencio >= t3.5 (micros).
void ModbusRTU::poll(){
  if(!m_serial) return;

  // Leer todo lo disponible
  while(m_serial->available()){
    int b = m_serial->read();
    if(b < 0) break;
    // Si el buffer se llena, los bytes extra se descartan (no se rompe la ejecución).
    // Alternativa: registrar overruns con regs_diag_inc(HR_DIAG_OVERRUNS).
    if(m_rxLen < sizeof(m_rxBuf)) m_rxBuf[m_rxLen++] = uint8_t(b);
    lastByteUs = micros();
  }

  // Si no hay nada, nada que hacer
  if(m_rxLen == 0) return;

  // Si pasó silencio >= t3.5, considerar trama completa
  uint32_t now = micros();
  if( (now - lastByteUs) >= t35_us ){
    // Procesar
    handleRequest(m_rxBuf, m_rxLen);
    clearRx();
  }
}

// ---------- Report Slave ID (0x11) ----------
void ModbusRTU::handleReportSlaveId(uint8_t unit){

  // Construye una respuesta con Vendor, Modelo y Versión firmware.
  // Formato: [unit][0x11][byteCount][slaveId][runIndicator][ascii...]
  char info[160];
  // Cadena tipo: VENDOR=..;MODEL=..;FW=..
  // Nota: las macros provienen de firmware_version.h

  // Componer cadena (evitar snprintf de gran tamaño en AVR si se prefiere)
    uint8_t asciiLen = fv_build_identity_ascii(info, sizeof(info));

  // Construcción de PDU
  uint8_t resp[256];
  resp[0] = unit;
  resp[1] = 0x11;
  // [2] = byteCount (rellenar después)
  uint8_t idx = 3;
  resp[idx++] = unit;         // slaveId (eco de la unidad direccionada)
  resp[idx++] = 0xFF;         // runIndicator (0xFF = en marcha)
  // Copiar ascii
  const uint8_t maxAscii = (uint8_t)(sizeof(resp) - idx - 2); // reserva para CRC en capa sendResponse
    if(asciiLen > maxAscii) asciiLen = maxAscii;
  memcpy(&resp[idx], info, asciiLen);
  idx += asciiLen;

  // Byte count incluye slaveId + runIndicator + ascii
  resp[2] = (uint8_t)(2 + asciiLen);
  sendResponse(resp, idx);
}

// ---------- Identify + Info (0x41 propietaria) ----------
void ModbusRTU::handleIdentifyBlinkAndInfo(uint8_t unit){
  // Disparar Identify por defecto
  regs_write_holding(HR_CMD_IDENT_SEGUNDOS, IDENTIFY_DEFAULT_SECS);
  // Construye respuesta tipo 0x11 pero con func=0x41

  char info[160];
    uint8_t asciiLen = fv_build_identity_ascii(info, sizeof(info));

  uint8_t resp[256];
  resp[0] = unit;
  resp[1] = 0x41; // función propietaria
  uint8_t idx = 3;
  resp[idx++] = unit;         // slaveId (eco de la unidad direccionada)
  resp[idx++] = 0xFF;         // runIndicator
  const uint8_t maxAscii = (uint8_t)(sizeof(resp) - idx - 2);
    if(asciiLen > maxAscii) asciiLen = maxAscii;
  memcpy(&resp[idx], info, asciiLen);
  idx += asciiLen;
  resp[2] = (uint8_t)(2 + asciiLen);
  sendResponse(resp, idx);
}
