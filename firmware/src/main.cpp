// -----------------------------------------------------------------------------
// main.cpp — Integración: Modbus RTU + BlinkIdent + SensorManager
// - Se delega la captura/normalización de datos a SensorManager (sin funciones locales).
// - SensorManager registra sensores (p.ej., MPU6050) y vuelca telemetría a registros Modbus.
// - Bucle no bloqueante: Modbus.poll() + ident.update() + sensorManager.pollAll().
// -----------------------------------------------------------------------------
#include <Arduino.h>
#include "config_pins.h"
#include <BlinkIdent.h>
#include <ModbusRTU.h>
#include <registersModbus.h>
#include <EepromUtils.h>
#include <SensorManager.h>
#include <SensorConfig.h>
#if SENSORS_MPU_ENABLED
#include <MPU6050Sensor.h>
#endif
#if SENSORS_LOAD_ENABLED
#include <LoadSensor.h>
#endif
#if SENSORS_WIND_ENABLED
#include <WindSpeedSensor.h>
#endif

// Identificación visual
static BlinkIdent ident(IDENT_LED_PIN);     // Instancia del patrón Identify en el pin configurado

// Servidor Modbus RTU
static ModbusRTU modbus_client;              // Esclavo Modbus RTU 

// Gestor de sensores y sensor(es) registrados
static SensorManager sensorManager;         // Orquestador de captura/normalización
#if SENSORS_MPU_ENABLED
static MPU6050Sensor sensor_mpu0;           // IMU MPU6050 (accel + gyro + temp interna + ángulos)
#endif
#if SENSORS_LOAD_ENABLED
static LoadSensor sensor_load0;             // Sensor de carga/corriente
#endif
#if SENSORS_WIND_ENABLED
static WindSpeedSensor sensor_wind0;        // Anemómetro analógico (0.4–2.0V → 0–32.4 m/s)
#endif

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

// Gestiona sólo cambios de factor de calibración desde Holding Registers (sin tara runtime)
static void apply_load_cal_from_registers(){
#if SENSORS_LOAD_ENABLED
  static uint16_t last_cal_seq  = 0;
  uint16_t cal_seq = regs_get_load_cal_write_seq();
  if (cal_seq != last_cal_seq){
    last_cal_seq = cal_seq;
    uint16_t v = 0;
    if (regs_read_holding(HR_LOAD_CAL_FACTOR_DECI, 1, &v)){
      float factor = ((float)v) / 10.0f;
      sensor_load0.setCalibrationFactor(factor);
    }
  }
#endif
}

void setup() {
  // Inicializa Serial USB para logs de debug (especialmente en Micro)
  #if defined(__AVR_ATmega32U4__)
    // Inicializa USB CDC a la misma velocidad declarada para Modbus
    Serial.begin(UART_BAUDRATE);
    while(!Serial && millis() < 2000); // Espera máx 2s para monitor serial
  #endif
  
  //Led para estado Identify
  pinMode(STATUS_LED_PIN, OUTPUT);
  digitalWrite(STATUS_LED_PIN, LOW);

  // Inicia UART hardware para Modbus RTU
  // MODBUS_SERIAL se autodetecta: Serial (UNO/Nano) o Serial1 (Micro/Leonardo/Mega)
    
  // Inicia Modbus RTU: usa el UART ya configurado y controla DE/RE del MAX485
  modbus_client.begin(MODBUS_SERIAL, UART_BAUDRATE, RS485_DERE_PIN);

  // Inicializa BlinkIdent
  ident.begin();                           // Configura pin del LED
  ident.start(3);                          // Arranque breve de cortesía (5 s)

  // Registrar e inicializar sensores (no crear lógica aquí)
#if SENSORS_MPU_ENABLED
  sensorManager.registerSensor(&sensor_mpu0);
#endif
#if SENSORS_LOAD_ENABLED
  sensorManager.registerSensor(&sensor_load0);
#endif
#if SENSORS_WIND_ENABLED
  sensorManager.registerSensor(&sensor_wind0);
#endif
  sensorManager.beginAll();
}

void loop() {
  // Procesa peticiones RTU y actualiza parpadeo de Identify
  modbus_client.poll();
  apply_ident_from_register();
  apply_load_cal_from_registers();
  ident.update();

  // Gestionar eventos de Guardar/Aplicar configuración
  {
    static uint16_t last_cfg_seq = 0;
    uint16_t seq = regs_get_save_apply_write_seq();
    if (seq != last_cfg_seq){
      last_cfg_seq = seq;
      uint16_t cmd = 0;
      if (regs_read_holding(HR_CMD_GUARDAR_APLICAR, 1, &cmd)){
        if (cmd == 0xA55A){
          // Guardar en EEPROM los parámetros persistentes: Unit ID (alias ya se persiste en regs_write_multi)
          uint16_t uid = regs_get_unit_id();
          if (uid >= 1 && uid <= 247){
            EepromUtils::writeUnitId(uid);
            regs_set_status(DEV_STATUS_CFG_DIRTY, false);
          }
        }
      }
    }
  }

  // Sensores: delegar al gestor (normaliza y vuelca registros)
  sensorManager.pollAll(millis());
}
