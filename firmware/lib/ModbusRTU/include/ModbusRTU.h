// -----------------------------------------------------------------------------
// ModbusRTU.h — Servidor Modbus RTU para AVR (UART + MAX485)
// Proyecto TFM: Supervisor de Cargas (RS-485 + Modbus RTU + MPU6050)
//
// Qué hace
// - Implementa un esclavo Modbus RTU minimalista con las funciones:
//   0x03 (Read Holding Registers), 0x04 (Read Input Registers), 0x06 (Write Single Register).
// - Gestiona broadcast (unidad=0) únicamente para 0x06: aplica la escritura sin responder.
//
// Cómo delimita tramas
// - Acumula bytes de UART en un buffer y considera la trama completa cuando detecta
//   silencio en el bus >= t3.5 caracteres (cálculo en begin() a partir de baud rate).
// - No usa interrupciones; se invoca poll() en cada loop() de Arduino.
//
// Contrato con el mapa de registros
// - Este servidor no conoce el detalle de los registros: delega en registersModbus.{h,cpp}
//   para leer/escribir valores y validar rangos. Ver funciones regs_*.
//
// Consideraciones de implementación
// - Endianness: Modbus define palabras de 16 bits en big-endian (MSB primero).
// - CRC: Modbus CRC16 polinomio 0xA001, acumulando LSB primero en la palabra.
// - Buffer RX: 64 bytes es suficiente para peticiones/respuestas habituales (hasta 32 regs).
//   Si se necesitara más, ajustar con cuidado para no impactar RAM.
// -----------------------------------------------------------------------------
#pragma once
#include <Arduino.h>

class ModbusRTU {
public:
  ModbusRTU() = default;

  // Inicializa el puerto serie y pin DE/RE del MAX485.
  // - serial: referencia al HardwareSerial (ej. Serial)
  // - baud: baudios (ej. 115200)
  // - derePin: pin que controla Driver Enable/Receiver Enable del MAX485
  // Además calcula t1.5 y t3.5 en microsegundos para delimitar tramas por silencio.
  void begin(HardwareSerial& serial, uint32_t baud, uint8_t derePin);

  // Procesa bytes entrantes; llamar en cada loop().
  // - Acumula bytes hasta detectar silencio >= t3.5 y entonces parsea la petición.
  // - Si la petición no va dirigida a mí (UNIT_ID), se descarta silenciosamente.
  // - En broadcast (unit=0), sólo se ejecuta 0x06 y no se responde.
  void poll();

private:
  HardwareSerial* m_serial = nullptr;
  uint8_t m_derePin = 0;

  uint8_t  m_rxBuf[64];
  uint8_t  m_rxLen = 0;
  uint32_t lastByteUs = 0;
  uint32_t t15_us = 0;
  uint32_t t35_us = 0;

  // Controla el transceptor RS-485: HIGH = transmitir, LOW = recibir.
  void setTransmit(bool en);
  // Vacía el buffer de recepción.
  void clearRx();
  // Parsea y atiende una PDU Modbus ya delimitada (incluye unit y CRC en el buffer original).
  void handleRequest(const uint8_t* p, uint8_t n);
  // Envía una respuesta RTU (PDU + CRC), conmutando DE/RE y esperando a que el UART vacíe TX.
  void sendResponse(const uint8_t* p, uint8_t n);
  // Envía una respuesta de excepción (funcion|0x80, código ex).
  void sendException(uint8_t unit, uint8_t func, uint8_t ex);

  // Funciones Modbus
  // Lee registros Holding (0x03) o Input (0x04) y construye la PDU de respuesta.
  void handleReadHolding(uint8_t unit, uint16_t start, uint16_t count, bool isInput);
  // Escribe un único Holding (0x06). En broadcast aplica y no responde.
  void handleWriteSingle(uint8_t unit, uint16_t reg, uint16_t value, bool isBroadcast);
};
