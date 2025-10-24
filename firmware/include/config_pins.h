// -----------------------------------------------------------------------------
// config_pins.h — Definición de pines y parámetros HW (UNO/NANO)
// Proyecto: TFM Supervisor de Cargas (RS-485 + Modbus RTU)
// Autor: Sergio Lobo
// Notas:
//  - Soporta Arduino UNO y Arduino NANO (ATmega328P).
//  - MAX485 con línea DE/RE configurable. Por defecto: D2.
//  - LED de estado: LED_BUILTIN (D13 en UNO/NANO), sobrescribible.
//  - MPU-6050 por I²C: A4(SDA) y A5(SCL) en UNO/NANO.
//  - Todos estos valores pueden sobreescribirse con -D en platformio.ini.
// -----------------------------------------------------------------------------
#pragma once
#include <Arduino.h>

// -----------------------------
// Detección de placa objetivo
// -----------------------------
#if defined(ARDUINO_AVR_UNO)
  #define TFM_BOARD_NAME "Arduino UNO"
#elif defined(ARDUINO_AVR_NANO)
  #define TFM_BOARD_NAME "Arduino NANO"
#else
  #define TFM_BOARD_NAME "Arduino (AVR genérico)"
#endif

// -----------------------------
// UART/RS-485
// -----------------------------
#ifndef TFM_UART_BAUD
  #define TFM_UART_BAUD 115200UL       // 8N1
#endif

// MAX485: pin digital que controla DE y RE (unidos)
// Sobrescribe con -D RS485_DERE_PIN=<n> en platformio.ini si quieres cambiarlo.
#ifndef RS485_DERE_PIN
  #define RS485_DERE_PIN 2            // por defecto D2
#endif

// -----------------------------
// LED de estado / identificación
// -----------------------------
#ifndef TFM_STATUS_LED_PIN
  #define TFM_STATUS_LED_PIN LED_BUILTIN   // D13 en UNO/NANO
#endif

// -----------------------------
// I2C (MPU-6050)
// -----------------------------
// UNO/NANO: A4 = SDA, A5 = SCL.
// Wire usa automáticamente estos pines, no necesitas setearlos manualmente.
// Los dejamos definidos solo a efectos documentales/consistencia.
#ifndef TFM_I2C_SDA_PIN
  #define TFM_I2C_SDA_PIN A4
#endif
#ifndef TFM_I2C_SCL_PIN
  #define TFM_I2C_SCL_PIN A5
#endif

// Dirección I2C típica del MPU-6050 (AD0 a GND → 0x68; a VCC → 0x69)
#ifndef MPU6050_I2C_ADDR
  #define MPU6050_I2C_ADDR 0x68
#endif

// -----------------------------
// Helpers en tiempo de compilación
// -----------------------------
#if !defined(RS485_DERE_PIN)
  #error "RS485_DERE_PIN no definido y no hay valor por defecto"
#endif