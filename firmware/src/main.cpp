// -----------------------------------------------------------------------------
// main.cpp — Demo mínima: espera activa para hacer blink de identificación
// - Sin Modbus, sin registros: sólo parpadeo de Identify mediante BlinkIdent.
// - "Espera activa" = bucle loop sin delays bloqueantes; update() gestiona tiempos.
// -----------------------------------------------------------------------------
#include <Arduino.h>
#include "config_pins.h"
#include <BlinkIdent.h>

// Instancia del identificador visual en el pin configurado
static BlinkIdent ident(IDENT_LED_PIN);

void setup() {
  // LED de estado opcional
  pinMode(STATUS_LED_PIN, OUTPUT);
  digitalWrite(STATUS_LED_PIN, LOW);

  // Inicializa el controlador de identificación
  ident.begin();

  // Arranca el patrón de identificación.
  // Nota: puedes ajustar la duración (segundos). Aquí ejemplo 15s.
  ident.start(15);
}

void loop() {
  // Espera activa: actualiza el patrón en cada iteración (no bloquea)
  ident.update();
}