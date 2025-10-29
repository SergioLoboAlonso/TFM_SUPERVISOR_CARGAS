// -----------------------------------------------------------------------------
// main.cpp — Integración: Modbus RTU + BlinkIdent (Identify)
// - Conecta la escritura del registro HR_CMD_IDENT_SEGUNDOS con el patrón BlinkIdent.
// - Bucle no bloqueante: Modbus.poll() + ident.update().
// -----------------------------------------------------------------------------
#include <Arduino.h>
#include "config_pins.h"
#include <BlinkIdent.h>
#include <ModbusRTU.h>
#include <registersModbus.h>

// Identificación visual
static BlinkIdent ident(IDENT_LED_PIN);     // Instancia del patrón Identify en el pin configurado
// Servidor Modbus RTU
static ModbusRTU mb_client;                 // Esclavo Modbus RTU sobre UART HW

// Seguimiento del último valor aplicado de HR_CMD_IDENT_SEGUNDOS
static uint16_t last_ident_secs = 0;        // Cache del último timeout de Identify

static void apply_ident_from_register(){     // Aplica cambios de HR_CMD_IDENT_SEGUNDOS a BlinkIdent
  static uint16_t last_seq = 0;             // Última secuencia observada
  uint16_t feedback = 0;                    // Lectura eco del registro (último valor escrito)
  if (!regs_read_holding(HR_CMD_IDENT_SEGUNDOS, 1, &feedback)) return;

  // Detecta evento de escritura real (incluyendo re‑escritura del mismo valor)
  uint16_t seq = regs_get_ident_write_seq();
  if (seq != last_seq) {
    last_seq = seq;
    if (feedback == 0) {
      // Solicitud explícita de parada
      if (ident.is_active()) ident.stop();
      last_ident_secs = 0;
    } else {
      // Nueva orden de Identify: iniciar o reiniciar
      ident.start(feedback);
      last_ident_secs = feedback;
    }
  }
  // Si no hay nueva escritura, no hacer nada: evita rearmado automático al expirar
}

void setup() {
  pinMode(STATUS_LED_PIN, OUTPUT);
  digitalWrite(STATUS_LED_PIN, LOW);

  Serial.begin(UART_BAUDRATE, SERIAL_8N1);  // UART para logs y Modbus
  
  // Inicia Modbus RTU en el UART hardware y controla DE/RE del MAX485
  mb_client.begin(Serial, UART_BAUDRATE, RS485_DERE_PIN);

  // Inicializa BlinkIdent
  ident.begin();                           // Configura pin del LED
  ident.start(1);                          // Arranque breve de cortesía (5 s)
}

void loop() {
  // Procesa peticiones RTU y actualiza parpadeo de Identify
  mb_client.poll();
  apply_ident_from_register();
  ident.update();
  
}