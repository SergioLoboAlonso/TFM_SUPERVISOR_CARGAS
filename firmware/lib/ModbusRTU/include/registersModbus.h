// -----------------------------------------------------------------------------
// registersModbus.h — Mapa de registros Modbus RTU conforme a la norma
// Proyecto TFM: Supervisor de Cargas (AVR + RS-485 + Modbus RTU + MPU6050)
//
// Convenciones generales
// - Direcciones en PDU son base 0 (norma Modbus). Se muestran referencias 3xxxx/4xxxx
//   a modo humano para identificar bancos Input (3xxxx) y Holding (4xxxx).
// - Input Registers (función 0x04) son de solo lectura; Holding (0x03/0x06) admiten
//   lectura y, si procede, escritura (según cada dirección).
// - Granularidad: 1 registro = 16 bits. Los valores físicos se escalan a enteros
//   para evitar float en MCU. Ver macros SCALE_*.
// - Endianness: cada palabra Modbus es big-endian (MSB→LSB). Si en futuro se usan
//   valores de 32 bits, se deberán componer dos registros contiguos MSW/LSW.
//
// Contrato de la API regs_*
// - regs_read_* devuelven true si TODA la ventana solicitada es válida; si cualquiera
//   de las direcciones cae fuera de rango o no es soportada, devuelven false.
// - regs_write_holding aplica una escritura de 16 bits y devuelve true si es válida.
// - Las funciones no bloquean y no realizan I/O de bajo nivel; actúan sobre un estado
//   en RAM que debe ser mantenido por capas superiores (ej. sensores, lógica).
// -----------------------------------------------------------------------------
#pragma once
#include <Arduino.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

// -----------------------------
// Escalados y constantes: convierten unidades físicas a enteros de 16 bits
// -----------------------------
#define SCALE_MDEG        100    // ángulos en 0.01°
#define SCALE_MG          1000   // aceleración en mg
#define SCALE_MDPS        1000   // gyro en mdps
#define SCALE_CELSIUS_mC  100    // temperatura en 0.01 °C

// -----------------------------
// Rangos máximos por trama: acotan peticiones del maestro para evitar desbordes
// -----------------------------
#define MAX_HOLDING_READ   32
#define MAX_INPUT_READ     32

// -----------------------------
// BLOQUE 1: Información de dispositivo (Holding 4xxxx, sólo lectura desde maestro)
// Dirección base 0 (equivalente 40001…)
// -----------------------------
#define HR_DEV_VENDOR_ID      0x0000  // 40001 R  Vendor (0x5446 = 'TF')
#define HR_DEV_PRODUCT_ID     0x0001  // 40002 R  Producto (0x4D30 = 'M0')
#define HR_DEV_HW_VERSION     0x0002  // 40003 R  HW version (major<<8 | minor)
#define HR_DEV_FW_VERSION     0x0003  // 40004 R  FW version (major<<8 | minor)
#define HR_DEV_UNIT_ID        0x0004  // 40005 R  Unit ID efectivo (eco)
#define HR_DEV_CAPS           0x0005  // 40006 R  Capacidades bitmask
#define HR_DEV_UPTIME_LO      0x0006  // 40007 R  Uptime s (LSW)
#define HR_DEV_UPTIME_HI      0x0007  // 40008 R  Uptime s (MSW)
#define HR_DEV_STATUS         0x0008  // 40009 R  Estado bitmask
#define HR_DEV_ERRORS         0x0009  // 40010 R  Errores bitmask

// -----------------------------
// BLOQUE 2: Configuración (Holding 4xxxx, lectura/escritura)
// -----------------------------
#define HR_CFG_BAUDRATE_CODE  0x0010  // 40017 R/W  0=9600,1=19200,2=38400,3=57600,4=115200
#define HR_CFG_MPU_LPF_HZ     0x0011  // 40018 R/W  Filtro MPU (Hz) codificado
#define HR_CFG_SAVE_APPLY     0x0012  // 40019 W    0=noop, 0xA55A=save, 0xB007=apply
#define HR_CMD_IDENT_SECS     0x0013  // 40020 W    Start Identify: segundos (0=stop)
#define HR_CFG_UNIT_ID        0x0014  // 40021 R/W  Unit ID (1..247) (persistente)
#define HR_CFG_RESERVED_END   0x001F  // reserva de 0x0015..0x001F

// -----------------------------
// BLOQUE 3: Medidas (Input 3xxxx, sólo lectura por maestro)
// Dirección base 0 (equivalente 30001…)
// -----------------------------
#define IR_ANGLE_X_mDEG       0x0000  // 30001 R  Ángulo X en 0.01°
#define IR_ANGLE_Y_mDEG       0x0001  // 30002 R  Ángulo Y en 0.01°
#define IR_TEMP_mC            0x0002  // 30003 R  Temp 0.01°C
#define IR_ACC_X_mG           0x0003  // 30004 R  Aceleración X en mg
#define IR_ACC_Y_mG           0x0004  // 30005 R  Aceleración Y en mg
#define IR_ACC_Z_mG           0x0005  // 30006 R  Aceleración Z en mg
#define IR_GYR_X_mdps         0x0006  // 30007 R  Gyro X en mdps
#define IR_GYR_Y_mdps         0x0007  // 30008 R  Gyro Y en mdps
#define IR_GYR_Z_mdps         0x0008  // 30009 R  Gyro Z en mdps
#define IR_SAMPLE_COUNT_LO    0x0009  // 30010 R  contador muestras (LSW)
#define IR_SAMPLE_COUNT_HI    0x000A  // 30011 R  contador muestras (MSW)
#define IR_FLAGS              0x000B  // 30012 R  flags de calidad (bitmask)
#define IR_RESERVED_END       0x001F  // reserva

// -----------------------------
// BLOQUE 4: Diagnóstico (Holding 4xxxx, lectura por maestro; escrituras internas)
// -----------------------------
#define HR_DIAG_RX_FRAMES     0x0020  // 40033 R  tramas RX OK
#define HR_DIAG_RX_CRC_ERR    0x0021  // 40034 R  tramas RX con CRC malo
#define HR_DIAG_RX_EXCPT      0x0022  // 40035 R  excepciones enviadas
#define HR_DIAG_TX_FRAMES     0x0023  // 40036 R  tramas TX OK
#define HR_DIAG_OVERRUNS      0x0024  // 40037 R  UART overruns
#define HR_DIAG_LAST_EXCPT    0x0025  // 40038 R  último código de excepción
#define HR_DIAG_RESERVED_END  0x002F  // reserva

// -----------------------------
// Límites de mapa (para validación rápida) — ambos extremos incluidos
// -----------------------------
#define HR_MIN_ADDR  0x0000
#define HR_MAX_ADDR  0x002F
#define IR_MIN_ADDR  0x0000
#define IR_MAX_ADDR  0x001F

// -----------------------------
// Máscaras de estado/errores/capacidades
// -----------------------------
enum : uint16_t {
  DEV_CAP_RS485   = (1u<<0),
  DEV_CAP_MPU6050 = (1u<<1),
  DEV_CAP_IDENT   = (1u<<2),
};

enum : uint16_t {
  DEV_STATUS_OK        = (1u<<0),
  DEV_STATUS_MPU_READY = (1u<<1),
  DEV_STATUS_CFG_DIRTY = (1u<<2),
};

enum : uint16_t {
  DEV_ERR_NONE      = 0,
  DEV_ERR_MPU_COMM  = (1u<<0),
  DEV_ERR_EEPROM    = (1u<<1),
  DEV_ERR_RANGE     = (1u<<2),
};

// -----------------------------
// API de acceso al mapa (implementación en registersModbus.cpp)
// - Devuelven true si operación válida, false si fuera de rango o ilegal.
// - Los buffers de salida son array de uint16_t (cada entrada = 1 registro Modbus).
// - Orden de palabra: el servidor aplica big-endian al serializar; aquí se usa uint16_t nativo.
// -----------------------------
void regs_init(void);

// Lecturas
bool regs_read_input (uint16_t addr, uint16_t count, uint16_t* out);    // 0x04
bool regs_read_holding(uint16_t addr, uint16_t count, uint16_t* out);   // 0x03

// Escrituras
bool regs_write_holding(uint16_t addr, uint16_t value);                  // 0x06 (single)

// Hooks para que otras capas (sensores/lógica) actualicen valores en tiempo real
void regs_set_angles_mdeg(int16_t ax, int16_t ay);
void regs_set_temp_mc(int16_t mc);
void regs_set_acc_mg(int16_t x, int16_t y, int16_t z);
void regs_set_gyr_mdps(int16_t x, int16_t y, int16_t z);
void regs_bump_sample_counter(void);

// Estadísticas/diagnóstico: permiten que la capa Modbus incremente contadores y flags
void regs_diag_inc(uint16_t reg_addr);
void regs_set_status(uint16_t mask, bool enable);
void regs_set_error (uint16_t mask, bool enable);

#ifdef __cplusplus
} // extern "C"
#endif
