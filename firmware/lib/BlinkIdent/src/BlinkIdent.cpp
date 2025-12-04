// -----------------------------------------------------------------------------
// BlinkIdent — Implementación
// 
// Módulo responsable de ejecutar un patrón de parpadeo de identificación
// no bloqueante sobre un pin (LED). El patrón actual es un "doble parpadeo"
// repetido dentro de una ventana de 1 segundo, y se mantiene activo
// durante un tiempo configurado (timeout en segundos).
// -----------------------------------------------------------------------------
#include <Arduino.h>
#include "BlinkIdent.h"
#include "config_pins.h"

// Patrón de doble parpadeo en una ventana de 1 segundo.
// Se define la activación del LED en dos ventanas cortas:
//  - 0 a 150 ms   ON
//  - 150 a 300 ms  OFF
//  - 300 a 450 ms  ON
//  - 450 a 1000 ms  OFF
// Devuelve true si el LED debe estar encendido para el instante (phaseMs) indicado.
static inline bool patternDoubleBlink(uint32_t phaseMs) {
	return (phaseMs < 150) || (phaseMs >= 300 && phaseMs < 450);
}

// Constructor: almacena el pin donde se actuará (debe ser un pin válido de salida).
BlinkIdent::BlinkIdent(uint8_t pin) : pin_(pin) {}

// Inicializa el pin en modo salida y deja el LED en estado inactivo.
void BlinkIdent::begin() {
	pinMode(pin_, OUTPUT);
	driveLed(false);
}

// Función que inicia el patrón de identificación durante "timeoutSeconds" segundos.
// No bloquea: únicamente se registran los tiempos de inicio y fin; el
// parpadeo se gobierna desde update(). Se realiza una activación inmediata
// para feedback visual instantáneo.
void BlinkIdent::start(uint16_t timeoutSeconds) {
	active_ = true;
	startMs_ = millis();
	timeoutMs_ = (uint32_t)timeoutSeconds * 1000UL;
	// Arranque inmediato en ON para feedback
	driveLed(LED_ACTIVE);
}

// Detiene el patrón y apaga el LED.
void BlinkIdent::stop() {
	active_ = false;
	driveLed(LED_INACTIVE);
}

// Debe llamarse de forma periódica (por ejemplo, en loop()).
// Calcula el tiempo transcurrido desde el inicio y:
//  - Si se supera el timeout, detiene el patrón.
//  - Si sigue activo, determina la fase dentro de una ventana de 1 s y
//    aplica el estado ON/OFF según el patrón de doble parpadeo.
void BlinkIdent::update() {
	if (!active_) return;
	uint32_t now = millis();
	uint32_t elapsed = now - startMs_;
	if (elapsed >= timeoutMs_) {
		stop();
		return;
	}

	uint32_t phase = elapsed % 1000UL; // ventana de 1s
	bool set = patternDoubleBlink(phase);
	driveLed(set);
}

// Aplica el estado lógico al pin del LED, respetando las macros de nivel
// activo/inactivo definidas en config_pins.h (LED_ACTIVE / LED_INACTIVE).
void BlinkIdent::driveLed(bool set) {
	digitalWrite(pin_, set ? LED_ACTIVE : LED_INACTIVE);
}
