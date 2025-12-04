// -----------------------------------------------------------------------------
// ModbusRTU.h — Servidor Modbus RTU para AVR (UART + MAX485)
// Proyecto TFM: Supervisor de Cargas (RS-485 + Modbus RTU + MPU6050)
//
// Qué hace
// - Implementa un esclavo Modbus RTU minimalista con las funciones:
//   0x03 (Read Holding Registers), 0x04 (Read Input Registers), 0x06 (Write Single Register),
//   0x11 (Report Slave ID — información de dispositivo, sin trigger Blink),
//   0x41 (Propietaria) — Identify + información (trigger Blink + respuesta informativa).
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
// - Buffer RX: 64 bytes es suficiente para peticiones/respuestas max de este sistema (hasta 32 regs).
//   Si se necesitara más, cuidado RAM.
// -----------------------------------------------------------------------------
#pragma once
#include <Arduino.h>

class ModbusRTU {
public:
  ModbusRTU() = default;

  // Inicializa el puerto serie y pin DE/RE del MAX485.
  // - serial: referencia al HardwareSerial (ej. Serial en Uno Serial1 en Micro)
  // - baud: baudios (ej. 115200)
  // - derePin: pin que controla Driver Enable/Receiver Enable del MAX485
  // Además calcula t1.5 y t3.5 en microsegundos para delimitar tramas por silencio.
  void begin(HardwareSerial& serial, uint32_t baud, uint8_t derePin); // Inicializa UART y pin DE/RE

  // Procesa bytes entrantes; llamar en cada loop().
  // - Acumula bytes hasta detectar silencio >= t3.5 y entonces ejecuta la petición.
  // - Si la petición no va dirigida a mí (UNIT_ID), se descarta.
  // - En broadcast (unit=0), sólo se ejecuta 0x06 y no se responde.
  void poll(); // Procesa tramas entrantes; llamar en cada loop()

private:
  HardwareSerial* m_serial = nullptr; // Puntero al puerto serie de hardware (Permite usar otras placas Arduino con múltiples UART)
  uint8_t m_derePin = 0;              // Pin para Driver Enable / Receiver Enable del MAX485
  uint8_t  m_rxBuf[64];               // Buffer de recepción de trama RTU
  uint8_t  m_rxLen = 0;               // Longitud actual del buffer RX
  uint32_t lastByteUs = 0;            // Timestamp (us) del último byte recibido
  uint32_t t15_us = 0;                // Tiempo de 1.5 caracteres (us) calculado en begin()
  uint32_t t35_us = 0;                // Tiempo de 3.5 caracteres (us) calculado en begin()

  // Controla el transceptor RS-485: HIGH = transmitir, LOW = recibir.
  void setTransmit(bool en);          // Controla el transceptor: true=TX, false=RX

  // Vacía el buffer de recepción.
  void clearRx();                     // Resetea punteros/longitud del buffer RX

  // Parsea y atiende una PDU Modbus ya delimitada (incluye unit y CRC en el buffer original).
  void handleRequest(const uint8_t* p, uint8_t n); // Atiende una PDU (incluida en buffer)

  // Envía una respuesta RTU (PDU + CRC), conmutando DE/RE y esperando a que el UART vacíe TX.
  void sendResponse(const uint8_t* p, uint8_t n);  // Serializa PDU+CRC y conmuta DE/RE

  // Envía una respuesta de excepción (funcion|0x80, código ex).
  void sendException(uint8_t unit, uint8_t func, uint8_t ex); // Respuesta de excepción

  // Funciones Modbus
  // Lee registros Holding (0x03) o Input (0x04) y construye la PDU de respuesta.
  void handleReadHolding(uint8_t unit, uint16_t start, uint16_t count, bool isInput); // 0x03/0x04
  // Escribe un único Holding (0x06). En broadcast aplica y no responde.
  void handleWriteSingle(uint8_t unit, uint16_t reg, uint16_t value, bool isBroadcast); // 0x06
  // Escribe múltiples Holding (0x10). En broadcast aplica y no responde.
  void handleWriteMultiple(uint8_t unit, uint16_t start, uint16_t count, const uint16_t* values, bool isBroadcast); // 0x10
  // Report Slave ID (0x11): devuelve cadena de identificación (vendor, modelo, fw)
  void handleReportSlaveId(uint8_t unit); // 0x11
  // Identify + Info (0x41): dispara Identify y devuelve la misma información que 0x11
  void handleIdentifyBlinkAndInfo(uint8_t unit); // 0x41
};
