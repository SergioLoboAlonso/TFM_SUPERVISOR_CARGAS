// -----------------------------------------------------------------------------
// config_pins.h — Definición de pines y parámetros HW (UNO/NANO)
// Proyecto: TFM Supervisor de Cargas (RS-485 + Modbus RTU)
// Autor: Sergio Lobo
// Notas:
//  - Soporte para Arduino UNO y Arduino NANO (ATmega328P).
//  - MAX485 con línea DE/RE configurable (por defecto: D2 en UNO, D4 en NANO).
//  - LED de estado por defecto: LED_BUILTIN (D13 en UNO), configurable.
//  - MPU-6050 por I²C: A4 (SDA) y A5 (SCL) en UNO/NANO.
//  - Todos los valores pueden ser sobreescritos con -D en platformio.ini.
// -----------------------------------------------------------------------------
// Se evitan inclusiones repetidas
#pragma once
#include <Arduino.h>

// -----------------------------
// Detección de placa objetivo
// -----------------------------
#if defined(ARDUINO_AVR_UNO)
  #define BOARD_NAME "Arduino UNO" // Uso habitual en desarrollo
#elif defined(ARDUINO_AVR_NANO)
  #define BOARD_NAME "Arduino NANO" // Alternativa habitual
#else
  #define BOARD_NAME "Arduino (AVR genérico)" // Identificador genérico de placa
#endif

// -----------------------------
// UART/RS-485
// -----------------------------
// El hardware serial en UNO/NANO utiliza D0 (RX) y D1 (TX).
// No debe emplearse para otros fines.

#ifndef UART_BAUDRATE
  #define UART_BAUDRATE 115200UL       // 8N1: 8 data bits, sin paridad, 1 bit de parada
#endif

// MAX485: pin digital que controla DE y RE (puenteados)
// Puede sobreescribirse con -D RS485_DERE_PIN=<n> en platformio.ini
#ifndef RS485_DERE_PIN
  #if defined(ARDUINO_AVR_NANO)
    #define RS485_DERE_PIN 4          // NANO: por defecto D4
  #else
    #define RS485_DERE_PIN 2          // UNO u otros: por defecto D2
  #endif
#endif

// -----------------------------
// LED de estado / identificación
// -----------------------------
#ifndef STATUS_LED_PIN
  #if defined(ARDUINO_AVR_NANO)
    #define STATUS_LED_PIN 12          // NANO: D12 por defecto
  #else
    #define STATUS_LED_PIN LED_BUILTIN // UNO: D13 (LED_BUILTIN)
  #endif
#endif

// LED de identificación por defecto: se utiliza el LED de la placa si no se define otro
#ifndef IDENT_LED_PIN
  #define IDENT_LED_PIN LED_BUILTIN // LED por defecto para identificación
#endif
// Definiciones de activación del LED de identificación, más visuales para saber si está activo o no

#ifndef LED_ACTIVE
  #define LED_ACTIVE HIGH // Nivel lógico para encender LED
#endif

#ifndef LED_INACTIVE
  #define LED_INACTIVE LOW // Nivel lógico para apagar LED
#endif

// -----------------------------
// I2C (MPU-6050)
// -----------------------------
// UNO/NANO: A4 = SDA, A5 = SCL.
// Wire utiliza automáticamente estos pines; no es necesario configurarlos manualmente.
// Se dejan definidos a modo de documentación.
#ifndef I2C_SDA_PIN
  #define I2C_SDA_PIN A4 // Pin SDA en UNO/NANO
#endif
#ifndef I2C_SCL_PIN
  #define I2C_SCL_PIN A5 // Pin SCL en UNO/NANO
#endif

// Dirección I2C del MPU-6050: AD0 a GND → 0x68; a VCC → 0x69.
// Si el pin AD0 queda flotante puede producirse fallo; en GY-521 suele quedar 0x68 por pull-down.
#ifndef MPU6050_I2C_ADDR
  #define MPU6050_I2C_ADDR 0x68 // Dirección I2C por defecto del MPU-6050
#endif

// -----------------------------
// Comprobaciones en tiempo de compilación
// -----------------------------
#if !defined(RS485_DERE_PIN)
  #error "RS485_DERE_PIN no definido y no hay valor por defecto"
#endif