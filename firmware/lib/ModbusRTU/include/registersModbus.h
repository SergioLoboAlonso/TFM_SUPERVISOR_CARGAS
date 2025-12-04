// -----------------------------------------------------------------------------
// registersModbus.h — Mapa de registros Modbus RTU conforme a la norma
// Proyecto TFM: Supervisor de Cargas (Arduino + RS-485 + Modbus RTU + MPU6050)
//
// Convenciones generales
// - Direcciones en PDU son base 0 (norma Modbus). Se muestran referencias 3xxxx/4xxxx
//   a modo humano para identificar bancos Input (3xxxx) y Holding (4xxxx).
// - Input Registers (función 0x04) son de solo lectura; Holding (0x03/0x06) admiten
//   lectura y, si procede, escritura (según cada dirección).
// - Resolución: 1 registro = 2 bytes -> 16 bits. Los valores físicos se escalan a enteros
//   para evitar float en MCU.
// - Cada palabra Modbus es big-endian (MSB→LSB). Si en futuro se usan
//   valores de 32 bits, se deberán componer dos registros contiguos MSW/LSW y leerlos siempre en bloque.
//
// Uso típico desde la capa Modbus:
// - Para lecturas: (0x04)
//   el servidor llamará regs_read_input/holding(addr,count,out) con
//   validación previa de límites. Si retorna false → Excepción Illegal Address.
// - Para escrituras (0x03/0x06):
//   regs_write_holding(addr,value) — true si aceptada;
//   false → Excepción Illegal Data Value/Address según proceda.
//
// Contrato de la API regs_*
// - regs_read_* devuelven true si TODA la ventana solicitada es válida; si cualquiera
//   de las direcciones cae fuera de rango o no es soportada, devuelven false.
// - regs_write_holding aplica una escritura de 16 bits y devuelve true si es válida.
// - Las funciones no bloquean, actúan sobre un estado
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
#define HR_INFO_VENDOR_ID      0x0000  // 40001 R  Vendor (0x5446 = 'TF')
#define HR_INFO_PRODUCTO_ID    0x0001  // 40002 R  Producto (0x4D30 = 'M0')
#define HR_INFO_VERSION_HW     0x0002  // 40003 R  HW version (major<<8 | minor)
#define HR_INFO_VERSION_FW     0x0003  // 40004 R  FW version (major<<8 | minor)
#define HR_INFO_ID_UNIDAD      0x0004  // 40005 R  Unit ID efectivo (eco)
#define HR_INFO_CAPACIDADES    0x0005  // 40006 R  Capacidades bitmask
#define HR_INFO_UPTIME_S_LO    0x0006  // 40007 R  Uptime s (LSW)
#define HR_INFO_UPTIME_S_HI    0x0007  // 40008 R  Uptime s (MSW)
#define HR_INFO_ESTADO         0x0008  // 40009 R  Estado bitmask
#define HR_INFO_ERRORES        0x0009  // 40010 R  Errores bitmask

// -----------------------------
// BLOQUE 2: Configuración (Holding 4xxxx, lectura/escritura)
// -----------------------------
#define HR_CFG_BAUDIOS         0x0010  // 40017 R    Código baudios (ESTÁTICO, sólo lectura): 0=9600,1=19200,2=38400,3=57600,4=115200
#define HR_CFG_MPU_FILTRO_HZ   0x0011  // 40018 R/W  Filtro MPU (Hz) codificado
#define HR_CMD_GUARDAR         0x0012  // 40019 W    0=noop, 0xA55A=save EEPROM
// Compatibilidad con nomenclatura antigua (APLICAR era un no-op):
#ifndef HR_CMD_GUARDAR_APLICAR
#define HR_CMD_GUARDAR_APLICAR HR_CMD_GUARDAR
#endif
#define HR_CMD_IDENT_SEGUNDOS  0x0013  // 40020 W    Start Identify: segundos (0=stop)
#define HR_CFG_ID_UNIDAD       0x0014  // 40021 R/W  Unit ID (1..247) (persistente)
#define HR_CFG_POLL_INTERVAL_MS 0x0015 // 40022 R/W  Intervalo global de muestreo (ms) para poll de sensores (min 10, max 5000)
#define HR_CFG_RESERVED_END    0x001F  // reserva de 0x0015..0x001F

// Calibración sensor de carga (Holding 4xxxx, lectura/escritura)
// - HR_LOAD_CAL_FACTOR_DECI: factor de calibración del HX711 en décimas (p. ej. 420.0 -> 4200)
#define HR_LOAD_CAL_FACTOR_DECI   0x0017  // 40024 R/W Factor de calibración * 10 (int16)

// -----------------------------
// BLOQUE 3: Medidas (Input 3xxxx, sólo lectura por maestro)
// Dirección base 0 (equivalente 30001…)
// -----------------------------
#define IR_MED_ANGULO_X_CDEG   0x0000  // 30001 R  Ángulo X en 0.01°
#define IR_MED_ANGULO_Y_CDEG   0x0001  // 30002 R  Ángulo Y en 0.01°
#define IR_MED_TEMPERATURA_CENTI 0x0002  // 30003 R  Temp 0.01°C
#define IR_MED_ACEL_X_mG       0x0003  // 30004 R  Aceleración X en mg
#define IR_MED_ACEL_Y_mG       0x0004  // 30005 R  Aceleración Y en mg
#define IR_MED_ACEL_Z_mG       0x0005  // 30006 R  Aceleración Z en mg
#define IR_MED_GIRO_X_mdps     0x0006  // 30007 R  Gyro X en mdps
#define IR_MED_GIRO_Y_mdps     0x0007  // 30008 R  Gyro Y en mdps
#define IR_MED_GIRO_Z_mdps     0x0008  // 30009 R  Gyro Z en mdps
#define IR_MED_MUESTRAS_LO     0x0009  // 30010 R  contador muestras (LSW)
#define IR_MED_MUESTRAS_HI     0x000A  // 30011 R  contador muestras (MSW)
#define IR_MED_FLAGS_CALIDAD   0x000B  // 30012 R  flags de calidad (bitmask)
#define IR_MED_PESO_KG         0x000C  // 30013 R  Peso/carga en kg (kg*100=no decimales)
#define IR_MED_WIND_SPEED_CMPS 0x000D  // 30014 R  Velocidad viento en cm/s (m/s * 100)
#define IR_MED_WIND_DIR_DEG    0x000E  // 30015 R  Dirección viento en grados (0-359)
// Estadísticas de ventana deslizante de 5 s (tumbling) — min/max/avg
#define IR_STAT_WIND_MIN_CMPS  0x000F  // 30016 R  Viento min (cm/s) ventana 5 s
#define IR_STAT_WIND_MAX_CMPS  0x0010  // 30017 R  Viento max (cm/s) ventana 5 s
#define IR_STAT_WIND_AVG_CMPS  0x0011  // 30018 R  Viento avg (cm/s) ventana 5 s

#define IR_STAT_ACC_X_MIN_mG   0x0012  // 30019 R  Accel X min (mg) ventana 5 s
#define IR_STAT_ACC_X_MAX_mG   0x0013  // 30020 R  Accel X max (mg) ventana 5 s
#define IR_STAT_ACC_X_AVG_mG   0x0014  // 30021 R  Accel X avg (mg) ventana 5 s
#define IR_STAT_ACC_Y_MIN_mG   0x0015  // 30022 R  Accel Y min (mg) ventana 5 s
#define IR_STAT_ACC_Y_MAX_mG   0x0016  // 30023 R  Accel Y max (mg) ventana 5 s
#define IR_STAT_ACC_Y_AVG_mG   0x0017  // 30024 R  Accel Y avg (mg) ventana 5 s
#define IR_STAT_ACC_Z_MIN_mG   0x0018  // 30025 R  Accel Z min (mg) ventana 5 s
#define IR_STAT_ACC_Z_MAX_mG   0x0019  // 30026 R  Accel Z max (mg) ventana 5 s
#define IR_STAT_ACC_Z_AVG_mG   0x001A  // 30027 R  Accel Z avg (mg) ventana 5 s

// Estadística de carga (peso): máximo de las últimas 100 muestras
#define IR_STAT_LOAD_MAX_KG    0x001B  // 30028 R  Máximo de las últimas 100 muestras (kg*100)

#define IR_RESERVED_END        0x001F  // reserva

// -----------------------------
// BLOQUE 4: Diagnóstico (Holding 4xxxx, lectura por maestro; escrituras internas)
// -----------------------------
#define HR_DIAG_TRAMAS_RX_OK     0x0020  // 40033 R  tramas RX OK
#define HR_DIAG_RX_CRC_ERROR     0x0021  // 40034 R  tramas RX con CRC malo
#define HR_DIAG_RX_EXCEPCIONES   0x0022  // 40035 R  excepciones enviadas
#define HR_DIAG_TRAMAS_TX_OK     0x0023  // 40036 R  tramas TX OK
#define HR_DIAG_DESBORDES_UART   0x0024  // 40037 R  UART overruns
#define HR_DIAG_ULTIMA_EXCEPCION 0x0025  // 40038 R  último código de excepción

// -----------------------------
// BLOQUE 5: Identidad extendida (Holding 4xxxx, sólo lectura)
// - Cadenas ASCII empaquetadas 2B por registro (MSB,LSB)
// - Longitud en bytes en *_LEN (0..8). Datos en *_STR0..*_STR3 (4 regs = 8 bytes)
// - Compatibilidad: HR_INFO_VENDOR_ID/PRODUCTO_ID siguen existiendo (2B)
// -----------------------------
#define HR_INFO_VENDOR_STR_LEN   0x0026  // 40039 R  bytes válidos en vendor (0..8)
#define HR_INFO_VENDOR_STR0      0x0027  // 40040 R  vendor bytes[0..1]
#define HR_INFO_VENDOR_STR1      0x0028  // 40041 R  vendor bytes[2..3]
#define HR_INFO_VENDOR_STR2      0x0029  // 40042 R  vendor bytes[4..5]
#define HR_INFO_VENDOR_STR3      0x002A  // 40043 R  vendor bytes[6..7]
#define HR_INFO_PRODUCT_STR_LEN  0x002B  // 40044 R  bytes válidos en product (0..8)
#define HR_INFO_PRODUCT_STR0     0x002C  // 40045 R  product bytes[0..1]
#define HR_INFO_PRODUCT_STR1     0x002D  // 40046 R  product bytes[2..3]
#define HR_INFO_PRODUCT_STR2     0x002E  // 40047 R  product bytes[4..5]
#define HR_INFO_PRODUCT_STR3     0x002F  // 40048 R  product bytes[6..7]

#define HR_DIAG_RESERVED_END     0x002F  // reserva

// -----------------------------
// BLOQUE 6: Alias de dispositivo (Holding 4xxxx, sólo lectura)
// - Alias ASCII (0..64 bytes) empaquetado 2B por registro (MSB,LSB)
// - Longitud en bytes en HR_ID_ALIAS_LEN (0..64)
// - Datos en HR_ID_ALIAS0..HR_ID_ALIAS31 (32 regs = 64 bytes)
// -----------------------------
#define HR_ID_ALIAS_LEN          0x0030  // 40049 R  bytes válidos en alias (0..64)
#define HR_ID_ALIAS0             0x0031  // 40050 R  alias bytes[0..1] (base)
// Rango de datos: 0x0031..0x0050 (32 registros)

// -----------------------------
// Límites de mapa (para validación rápida) — ambos extremos incluidos
// -----------------------------
#define HR_MIN_ADDR  0x0000
#define HR_MAX_ADDR  0x0050
#define IR_MIN_ADDR  0x0000
#define IR_MAX_ADDR  0x001F

// -----------------------------
// Máscaras de estado/errores/capacidades
// -----------------------------

// Duración por defecto del Identify cuando se solicita por 0x11 (segundos)
#ifndef IDENTIFY_DEFAULT_SECS
#define IDENTIFY_DEFAULT_SECS 10
#endif
enum {
  DEV_CAP_RS485   = (1u<<0), // Soporta comunicación RS‑485
  DEV_CAP_MPU6050 = (1u<<1), // Integra sensor MPU‑6050
  DEV_CAP_IDENT   = (1u<<2), // Soporta Identify (parpadeo LED)
  DEV_CAP_WIND    = (1u<<3), // Anemómetro analógico de velocidad de viento
  DEV_CAP_LOAD    = (1u<<4), // Sensor de carga/peso HX711
};

enum {
  DEV_STATUS_OK        = (1u<<0), // Estado general OK
  DEV_STATUS_MPU_READY = (1u<<1), // Lecturas del MPU disponibles
  DEV_STATUS_CFG_DIRTY = (1u<<2), // Config pendiente de aplicar/guardar
};

enum {
  DEV_ERR_NONE      = 0,        // Sin errores
  DEV_ERR_MPU_COMM  = (1u<<0),  // Error de comunicación con MPU
  DEV_ERR_EEPROM    = (1u<<1),  // Error acceso EEPROM
  DEV_ERR_RANGE     = (1u<<2),  // Valor fuera de rango
};

// -----------------------------
// API de acceso al mapa (implementación en registersModbus.cpp)
// - Devuelven true si operación válida, false si fuera de rango o ilegal.
// - Los buffers de salida son array de uint16_t (cada entrada = 1 registro Modbus).
// - Orden de palabra: el servidor aplica big-endian al serializar; aquí se usa uint16_t nativo.
// - Concurrencia: no bloquean; deben llamarse desde el bucle principal (no ISR a menos que se garantice seguridad).
// -----------------------------
void regs_init(void);

// Lecturas

// 0x04: Lee 'count' registros Input consecutivos a partir de 'addr' en 'out'.
// Precondición: 'out' apunta a buffer con al menos 'count' uint16_t.
bool regs_read_input (uint16_t addr, uint16_t count, uint16_t* out);
// 0x03: Lee 'count' registros Holding consecutivos a partir de 'addr' en 'out'.
// Incluye Info, Config y Diagnóstico. Algunas direcciones devuelven "eco" del último valor escrito.
bool regs_read_holding(uint16_t addr, uint16_t count, uint16_t* out);

// Escrituras
// Secuencia de escrituras en HR_CMD_IDENT_SEGUNDOS para detectar eventos
uint16_t regs_get_ident_write_seq();
// Secuencia de escrituras en HR_CMD_GUARDAR para detectar eventos (save)
uint16_t regs_get_save_write_seq();
// Compatibilidad con API anterior: alias al contador actual
static inline uint16_t regs_get_save_apply_write_seq(){ return regs_get_save_write_seq(); }

// 0x06 (single): Escribe un registro Holding en 'addr' con 'value'. Validaciones:
//  - HR_CFG_BAUDIOS: 0..4 (códigos de baudios)
//  - HR_CFG_MPU_FILTRO_HZ: rango codificado (p.ej. <=200)
//  - HR_CFG_ID_UNIDAD: 1..247
//  - HR_CMD_IDENT_SEGUNDOS: cualquier valor (0=stop)
//  - HR_CMD_GUARDAR: 0xA55A (persistir UnitID y Alias a EEPROM)
bool regs_write_holding(uint16_t addr, uint16_t value);

// 0x10 (multiple): Escribe 'count' registros Holding consecutivos a partir de 'addr'.
// Devuelve true si todas las escrituras son válidas. Puede aplicar lógica especial
// para bloques (p.ej., alias: HR_ID_ALIAS_LEN + datos empaquetados).
bool regs_write_multi(uint16_t addr, uint16_t count, const uint16_t* values);

// Hooks para que otras capas (sensores/lógica) actualicen valores en tiempo real
// Ángulos X/Y en décimas de grado (mdeg)
void regs_set_angles_mdeg(int16_t ax, int16_t ay);
void regs_set_temp_mc(int16_t mc);
void regs_set_acc_mg(int16_t x, int16_t y, int16_t z);
void regs_set_gyr_mdps(int16_t x, int16_t y, int16_t z);
// Peso/carga en kg (int16, rango aproximado ±327.67 kg)
// Ej.: 12.34 kg -> 1234
void regs_set_kg_load(int16_t kg_load);

// Velocidad y dirección del viento
// - speed_cmps: velocidad en cm/s (m/s * 100); ej: 3.45 m/s -> 345
// - dir_deg: dirección en grados 0-359 (0=Norte, 90=Este, 180=Sur, 270=Oeste)
void regs_set_wind(uint16_t speed_cmps, uint16_t dir_deg);

// Estadísticas de 5 s: setters para publicar a los registros
// Viento (cm/s)
void regs_set_wind_stats(uint16_t min_cmps, uint16_t max_cmps, uint16_t avg_cmps);
// Aceleración (mg) — orden: X(max,min,avg), Y(max,min,avg), Z(max,min,avg)
void regs_set_accel_stats(int16_t x_max, int16_t x_min, int16_t x_avg,
                          int16_t y_max, int16_t y_min, int16_t y_avg,
                          int16_t z_max, int16_t z_min, int16_t z_avg);

// Incrementa contador de muestras (32 bits expuesto como L/H en IR_MED_MUESTRAS_*)
void regs_bump_sample_counter(void);

// Estadísticas/diagnóstico: permiten que la capa Modbus incremente contadores y flags
void regs_diag_inc(uint16_t reg_addr);
void regs_set_status(uint16_t mask, bool enable);
void regs_set_error (uint16_t mask, bool enable);

// Consultas rápidas del estado
uint16_t regs_get_unit_id();

// Lectura de configuración desde registro Holding (intervalo global de muestreo)
uint16_t regs_get_cfg_poll_interval_ms();

// Secuencias de escritura para calibración de carga (detección de eventos)
uint16_t regs_get_load_cal_write_seq();


#ifdef __cplusplus
} // extern "C"
#endif
