// -----------------------------------------------------------------------------
// registersModbus.cpp — Implementación del mapa de registros Modbus RTU
//
// Responsabilidad
// - Mantener el estado de los registros Modbus en RAM (struct R)
// - Exponer funciones regs_* para lectura/escritura y diagnóstico
// - No hace I/O de hardware; otras capas deben alimentar los hooks (ángulos, temp, etc.)
//
// Notas
// - HW/FW/UNIT_ID se pueden inyectar por defines de compilación.
// - Los valores físicos están escalados (ver registersModbus.h) y se guardan en int16.
// - En escrituras inválidas se marca R.errors con DEV_ERR_RANGE.
// -----------------------------------------------------------------------------
#include "registersModbus.h"
#include <string.h>
#include "firmware_version.h" // Unifica versión HW/FW desde cabecera común
#include "config_pins.h"      // UART_BAUDRATE de compilación
#include <EepromUtils.h>       // Lectura de UnitID/Serial/Alias persistentes

// -----------------------------
// Defaults de compilación
// -----------------------------
// Estas macros pueden inyectarse desde platformio.ini (build_flags) para personalizar
// UnitID y versiones HW/FW en tiempo de compilación.
#ifndef UNIT_ID
  #define UNIT_ID 10      // Unit ID por defecto (1..247)
#endif
// Versionado ahora proviene de firmware_version.h (FW_VERSION_*, HW_REV)

// -----------------------------
// Estado interno
// -----------------------------
// Estado interno del dispositivo. Representa el "mapa" que el maestro ve.
// Las unidades/formatos siguen el contrato de registersModbus.h
static struct {
  // Info
  uint16_t vendor_id   = 0x4C6F;                 // 'L''o' (LoBo)
  uint16_t product_id  = 0x426F;                 // 'B''o' (LoBo)
  uint16_t hw_version  = (uint16_t)(((HW_VERSION_MAJOR) & 0xFF) << 8) | ((HW_VERSION_MINOR) & 0xFF); // HW: mayor.menor (parche se expone en Identify)
  uint16_t fw_version  = (uint16_t)((FW_VERSION_GLOBAL & 0xFF) << 8) | (FW_VERSION_MINOR & 0xFF); // FW: mayor/menor (parche via Identify)
  uint16_t unit_id     = UNIT_ID;                // Unit ID efectivo
  uint16_t caps        = (DEV_CAP_RS485 | DEV_CAP_IDENT 

    #if defined(SENSORS_MPU_ENABLED) && SENSORS_MPU_ENABLED
                         | DEV_CAP_MPU6050
#endif
#if defined(SENSORS_WIND_ENABLED) && SENSORS_WIND_ENABLED
                         | DEV_CAP_WIND
#endif
                         ); // Capacidades según build_flags (añade WIND si definido)

  uint16_t status      = DEV_STATUS_OK;          // Flags de estado
  uint16_t errors      = DEV_ERR_NONE;           // Flags de error

  // Config
  uint16_t baud_code   = 
#if   UART_BAUDRATE == 9600
  0
#elif UART_BAUDRATE == 19200
  1
#elif UART_BAUDRATE == 38400
  2
#elif UART_BAUDRATE == 57600
  3
#else
  4
#endif
  ;                      // Código de baudios (compilación)
  uint16_t mpu_lpf_hz  = 42;                     // ejemplo codificado
  uint16_t save  = 0;                      // Último comando de guardar
  uint16_t save_write_seq = 0;             // Secuencia de escrituras en HR_CMD_GUARDAR
  uint16_t ident_secs  = 0;                      // Timeout de identify (segundos)
  uint16_t ident_write_seq = 0;                  // Secuencia de escrituras en HR_CMD_IDENT_SEGUNDOS
  uint16_t poll_interval_ms = 100;               // Intervalo global de muestreo (ms)

  // Medidas
  int16_t  ang_x_mdeg  = 0;
  int16_t  ang_y_mdeg  = 0;
  int16_t  temp_mc     = 0;
  int16_t  acc_x_mg    = 0;
  int16_t  acc_y_mg    = 0;
  int16_t  acc_z_mg    = 0;
  int16_t  gyr_x_mdps  = 0;
  int16_t  gyr_y_mdps  = 0;
  int16_t  gyr_z_mdps  = 0;
  int16_t  load_kg     = 0;                      // Peso/carga en kg (kg*100=no decimales)
  uint16_t wind_speed_cmps = 0;                  // Velocidad viento en cm/s (m/s * 100)
  uint16_t wind_dir_deg = 0;                     // Dirección viento en grados (0-359)
  uint32_t sample_cnt  = 0;                      // Contador de muestras (32 bits)

  // Estadísticas 5 s
  // Viento (cm/s)
  uint16_t wind_min_cmps = 0;
  uint16_t wind_max_cmps = 0;
  uint16_t wind_avg_cmps = 0;
  // Aceleración (mg)
  int16_t acc_x_min_mg = 0, acc_x_max_mg = 0, acc_x_avg_mg = 0;
  int16_t acc_y_min_mg = 0, acc_y_max_mg = 0, acc_y_avg_mg = 0;
  int16_t acc_z_min_mg = 0, acc_z_max_mg = 0, acc_z_avg_mg = 0;

  // Diagnóstico
  uint16_t rx_frames   = 0;                      // Tramas RX OK
  uint16_t rx_crc_err  = 0;                      // Tramas RX con CRC erróneo
  uint16_t rx_excpt    = 0;                      // Excepciones enviadas
  uint16_t tx_frames   = 0;                      // Tramas TX OK
  uint16_t overruns    = 0;                      // Desbordes UART
  uint16_t last_excpt  = 0;                      // Último código de excepción
  // Alias (cargado bajo demanda desde EEPROM)
  uint16_t alias_len   = 0;                      // Longitud de alias (0..64)
  char     alias_buf[65] = {0};                  // Alias NUL
  bool     alias_loaded = false;                 // Flag de carga diferida
} R;

// -----------------------------
// Utilidades para empaquetado de cadenas ASCII en registros Modbus
// -----------------------------
/**
 * @brief Calcula la longitud de una cadena con límite de 8 caracteres
 * 
 * Recorre la cadena contando caracteres hasta encontrar NUL o alcanzar
 * el límite de 8 bytes. Útil para cadenas cortas de identificación.
 * 
 * @param s Puntero a la cadena ASCII terminada en NUL (puede ser nullptr)
 * @return Longitud efectiva de la cadena (0..8)
 * 
 * @note Si s es nullptr, retorna 0
 * @note Limita la longitud máxima a 8 caracteres independientemente del tamaño real
 */
static inline uint8_t str_len_cap8(const char* s) {
  uint8_t length = 0;
  
  // Contar caracteres hasta NUL o límite de 8
  while (s && *s && length < 8) {
    length++;
    s++;
  }
  
  return length;
}

/**
 * @brief Empaqueta 2 caracteres ASCII de una cadena en un registro de 16 bits
 * 
 * Cada registro Modbus (16 bits) puede contener 2 bytes ASCII. Esta función
 * extrae los dos caracteres correspondientes al índice de registro especificado
 * y los empaqueta en formato big-endian (MSB primero).
 * 
 * Ejemplo: "HELLO" con idx=0 → 'H'(0x48) en MSB, 'E'(0x45) en LSB → 0x4845
 *          "HELLO" con idx=1 → 'L'(0x4C) en MSB, 'L'(0x4C) en LSB → 0x4C4C
 *          "HELLO" con idx=2 → 'O'(0x4F) en MSB, 0x00 en LSB → 0x4F00
 * 
 * @param s Puntero a la cadena ASCII terminada en NUL (puede ser nullptr)
 * @param idx Índice del registro a empaquetar (0..N). Cada índice extrae 2 bytes:
 *            idx=0 → bytes [0..1], idx=1 → bytes [2..3], idx=2 → bytes [4..5], etc.
 * @return Valor de 16 bits con los dos caracteres empaquetados (big-endian)
 * 
 * @note Si s es nullptr, retorna 0x0000
 * @note Si la cadena termina antes de llenar el registro, los bytes faltantes son 0x00
 * @note El byte más significativo (MSB) contiene el primer carácter, el LSB el segundo
 */
static inline uint16_t pack_word2(const char* s, uint8_t idx) {
  uint8_t byte_msb = 0;  // Byte más significativo (primer carácter)
  uint8_t byte_lsb = 0;  // Byte menos significativo (segundo carácter)
  
  if (s) {
    // Calcular posición del primer byte de este registro
    uint8_t byte_offset = idx * 2;
    
    // Avanzar hasta la posición inicial (idx * 2 caracteres)
    uint8_t current_pos = 0;
    while (current_pos < byte_offset && *s) {
      s++;
      current_pos++;
    }
    
    // Extraer primer byte (MSB)
    if (*s) {
      byte_msb = (uint8_t)(*s);
      s++;
    }
    
    // Extraer segundo byte (LSB)
    if (*s) {
      byte_lsb = (uint8_t)(*s);
    }
  }
  
  // Empaquetar en formato big-endian: MSB en bits altos, LSB en bits bajos
  return (uint16_t)((byte_msb << 8) | byte_lsb);
}

// -----------------------------
// Utilidades internas
// -----------------------------
static inline uint16_t uptime_lo() {
  return (uint16_t)((millis()/1000UL) & 0xFFFF);
}
static inline uint16_t uptime_hi() {
  return (uint16_t)(((millis()/1000UL) >> 16) & 0xFFFF);
}
// Comprueba si [addr, addr+count-1] cae dentro de [min_a, max_a] 
//(evitar que te pidan la direccion de utlimo registro y otras 4, cae fuera de array)
static inline bool in_range(uint16_t addr, uint16_t min_a, uint16_t max_a, uint16_t count){
  if (addr < min_a) return false;
  if (addr > max_a) return false;
  if ((uint32_t)addr + count - 1 > max_a) return false;
  return true;
}

// Carga del alias desde EEPROM (o valor por defecto si no provisionado)
static inline void ensure_alias_loaded(){
  if (!R.alias_loaded){
    uint16_t l = 0;
    EepromUtils::readAlias(R.alias_buf, l);
    if (l > 64) l = 64;
    R.alias_len = l;
    R.alias_loaded = true;
  }
}

// -----------------------------
// Inizialización de estados manualmente
// -----------------------------
/**
 * @brief Inicializa el estado de los registros Modbus
 * 
 * Limpia estados transitorios y flags de error. Mantiene los valores
 * de vendor, product y versiones. Fuerza la recarga del alias desde EEPROM
 * en la próxima lectura.
 * 
 * @note Debe llamarse durante la inicialización del sistema
 */
void regs_init(void){
  // Limpia estados transitorios si aplica; mantiene vendor/product/versiones
  R.status = (DEV_STATUS_OK);
  R.errors = DEV_ERR_NONE;
  // Cargar UnitID y Alias desde EEPROM en arranque para disponer de identidad completa de inmediato
  // UnitID: aplicar directamente si es válido (1..247) sin marcar CFG_DIRTY
  EepromUtils::begin();
  uint16_t uid = EepromUtils::readUnitId();

  if (uid >= 1 && uid <= 247) R.unit_id = uid;
  
  R.alias_loaded = false;   // asegurar que ensure_alias_loaded() realiza la carga
  ensure_alias_loaded();    // readAlias() limitará longitud y NUL-terminará
}

// -----------------------------
// Lecturas
// -----------------------------
/**
 * @brief Lee registros de entrada (Input Registers) del dispositivo Modbus
 * 
 * Esta función lee un número especificado de registros de entrada consecutivos
 * (función 0x04) que contienen datos de telemetría en tiempo real (ángulos,
 * temperatura, aceleración, giroscopio, etc.).
 * 
 * @param addr Dirección inicial de los registros de entrada a leer
 * @param count Número de registros de entrada consecutivos a leer
 * @param out Puntero al búfer donde se almacenarán los valores leídos.
 *            El búfer debe ser suficientemente grande para contener 'count' valores uint16_t.
 * 
 * @return true si la operación de lectura fue exitosa
 * @return false si la operación falló (dirección inválida, count fuera de rango, etc.)
 * 
 * @note Los registros de entrada son de solo lectura y contienen datos medidos
 * @note El rango válido es IR_MIN_ADDR a IR_MAX_ADDR
 * @note count debe estar entre 1 y MAX_INPUT_READ
 */
// 0x04 — Input Registers: sólo lectura
bool regs_read_input(uint16_t addr, uint16_t count, uint16_t* out){//addr dirección, count cantidad de registros, out es hexa concat fomateado

  if (count==0 || count>MAX_INPUT_READ) return false; // evitar 0 medidas y peticiones largas
  if (!in_range(addr, IR_MIN_ADDR, IR_MAX_ADDR, count)) return false;//Evitar rangos invalidos

  for (uint16_t i=0;i<count;i++){
    uint16_t a = addr + i;
    switch(a){//En caso de añadir nuevos registros debe hacerse en el orden de registers.h
      case IR_MED_ANGULO_X_CDEG:    out[i] = (uint16_t)R.ang_x_mdeg; break;
      case IR_MED_ANGULO_Y_CDEG:    out[i] = (uint16_t)R.ang_y_mdeg; break;
      case IR_MED_TEMPERATURA_CENTI:out[i] = (uint16_t)R.temp_mc;    break;
      case IR_MED_ACEL_X_mG:        out[i] = (uint16_t)R.acc_x_mg;   break;
      case IR_MED_ACEL_Y_mG:        out[i] = (uint16_t)R.acc_y_mg;   break;
      case IR_MED_ACEL_Z_mG:        out[i] = (uint16_t)R.acc_z_mg;   break;
      case IR_MED_GIRO_X_mdps:      out[i] = (uint16_t)R.gyr_x_mdps; break;
      case IR_MED_GIRO_Y_mdps:      out[i] = (uint16_t)R.gyr_y_mdps; break;
      case IR_MED_GIRO_Z_mdps:      out[i] = (uint16_t)R.gyr_z_mdps; break;
      case IR_MED_PESO_KG:          out[i] = (uint16_t)R.load_kg;  break;
      case IR_MED_WIND_SPEED_CMPS:  out[i] = R.wind_speed_cmps; break;
      case IR_MED_WIND_DIR_DEG:     out[i] = R.wind_dir_deg; break;
  // Estadísticas de 5 s
  case IR_STAT_WIND_MIN_CMPS:   out[i] = R.wind_min_cmps; break;
  case IR_STAT_WIND_MAX_CMPS:   out[i] = R.wind_max_cmps; break;
  case IR_STAT_WIND_AVG_CMPS:   out[i] = R.wind_avg_cmps; break;
  case IR_STAT_ACC_X_MIN_mG:    out[i] = (uint16_t)R.acc_x_min_mg; break;
  case IR_STAT_ACC_X_MAX_mG:    out[i] = (uint16_t)R.acc_x_max_mg; break;
  case IR_STAT_ACC_X_AVG_mG:    out[i] = (uint16_t)R.acc_x_avg_mg; break;
  case IR_STAT_ACC_Y_MIN_mG:    out[i] = (uint16_t)R.acc_y_min_mg; break;
  case IR_STAT_ACC_Y_MAX_mG:    out[i] = (uint16_t)R.acc_y_max_mg; break;
  case IR_STAT_ACC_Y_AVG_mG:    out[i] = (uint16_t)R.acc_y_avg_mg; break;
  case IR_STAT_ACC_Z_MIN_mG:    out[i] = (uint16_t)R.acc_z_min_mg; break;
  case IR_STAT_ACC_Z_MAX_mG:    out[i] = (uint16_t)R.acc_z_max_mg; break;
  case IR_STAT_ACC_Z_AVG_mG:    out[i] = (uint16_t)R.acc_z_avg_mg; break;
      case IR_MED_MUESTRAS_LO:      out[i] = (uint16_t)(R.sample_cnt & 0xFFFF); break;
      case IR_MED_MUESTRAS_HI:      out[i] = (uint16_t)((R.sample_cnt>>16) & 0xFFFF); break;
      case IR_MED_FLAGS_CALIDAD:     out[i] = 0; break; // placeholder de calidad
          default:                 out[i] = 0; break; // reservas → 0 para estabilidad
    }
  }
  return true;
}
/**
 * @brief Lee registros holding del dispositivo Modbus
 * 
 * Esta función lee un número especificado de registros holding consecutivos
 * comenzando desde la dirección dada y almacena los valores en el búfer de salida.
 * 
 * @param addr Dirección inicial de los registros holding a leer
 * @param count Número de registros holding consecutivos a leer
 * @param out Puntero al búfer donde se almacenarán los valores de registros leídos.
 *            El búfer debe ser suficientemente grande para contener 'count' valores uint16_t.
 * 
 * @return true si la operación de lectura fue exitosa
 * @return false si la operación de lectura falló (dirección inválida, error de comunicación, etc.)
 * 
 * @note El  es responsable de asegurar que el búfer de salida tenga espacio suficiente
 * @note El rango de direcciones y la validez del count deben verificarse antes de llamar esta función
 */
// 0x03 — Holding Registers: info, config y diagnóstico
bool regs_read_holding(uint16_t addr, uint16_t count, uint16_t* out){
  if (count==0 || count>MAX_HOLDING_READ) return false;
  if (!in_range(addr, HR_MIN_ADDR, HR_MAX_ADDR, count)) return false;
  for (uint16_t i=0;i<count;i++){
    uint16_t acceso_estructura = addr + i;
    switch(acceso_estructura){
      
      // Info
      case HR_INFO_VENDOR_ID:      out[i] = R.vendor_id;   break;
      case HR_INFO_PRODUCTO_ID:    out[i] = R.product_id;  break;
      case HR_INFO_VERSION_HW:     out[i] = R.hw_version;  break;
      case HR_INFO_VERSION_FW:     out[i] = R.fw_version;  break;
      case HR_INFO_ID_UNIDAD:      out[i] = R.unit_id;     break;
      case HR_INFO_CAPACIDADES:    out[i] = R.caps;        break;
      case HR_INFO_UPTIME_S_LO:    out[i] = uptime_lo();   break;
      case HR_INFO_UPTIME_S_HI:    out[i] = uptime_hi();   break;
      case HR_INFO_ESTADO:         out[i] = R.status;      break;
      case HR_INFO_ERRORES:        out[i] = R.errors;      break;

      // Config
      case HR_CFG_BAUDIOS:         out[i] = R.baud_code;  break;
      case HR_CFG_MPU_FILTRO_HZ:   out[i] = R.mpu_lpf_hz; break;
      case HR_CMD_GUARDAR:         out[i] = R.save; break; // eco último valor
      case HR_CMD_IDENT_SEGUNDOS:  out[i] = R.ident_secs; break; // eco último valor
      case HR_CFG_ID_UNIDAD:       out[i] = R.unit_id;    break;
  case HR_CFG_POLL_INTERVAL_MS:out[i] = R.poll_interval_ms; break;

      // Diagnóstico
      case HR_DIAG_TRAMAS_RX_OK:     out[i] = R.rx_frames;  break;
      case HR_DIAG_RX_CRC_ERROR:     out[i] = R.rx_crc_err; break;
      case HR_DIAG_RX_EXCEPCIONES:   out[i] = R.rx_excpt;   break;
      case HR_DIAG_TRAMAS_TX_OK:     out[i] = R.tx_frames;  break;
      case HR_DIAG_DESBORDES_UART:   out[i] = R.overruns;   break;
      case HR_DIAG_ULTIMA_EXCEPCION: out[i] = R.last_excpt; break;

      // Identidad extendida (vendor/product ASCII, 0..8 bytes)
      case HR_INFO_VENDOR_STR_LEN:  out[i] = str_len_cap8(VENDOR_NAME); break;
      case HR_INFO_VENDOR_STR0:     out[i] = pack_word2(VENDOR_NAME, 0); break;
      case HR_INFO_VENDOR_STR1:     out[i] = pack_word2(VENDOR_NAME, 1); break;
      case HR_INFO_VENDOR_STR2:     out[i] = pack_word2(VENDOR_NAME, 2); break;
      case HR_INFO_VENDOR_STR3:     out[i] = pack_word2(VENDOR_NAME, 3); break;
      case HR_INFO_PRODUCT_STR_LEN: out[i] = str_len_cap8(MODEL_NAME); break;
      case HR_INFO_PRODUCT_STR0:    out[i] = pack_word2(MODEL_NAME, 0); break;
      case HR_INFO_PRODUCT_STR1:    out[i] = pack_word2(MODEL_NAME, 1); break;
      case HR_INFO_PRODUCT_STR2:    out[i] = pack_word2(MODEL_NAME, 2); break;
      case HR_INFO_PRODUCT_STR3:    out[i] = pack_word2(MODEL_NAME, 3); break;

      // Alias ASCII (0..64B) — longitud + datos empaquetados 2B/reg
      case HR_ID_ALIAS_LEN:
        out[i] = R.alias_len;
        break;

      //Edge puede leer cualquier registro del alias, debemos obligar que siempre pida desde el inicio
      default:
        // Rango de alias: HR_ID_ALIAS0..HR_ID_ALIAS0+31 (32 registros)
        if (acceso_estructura >= HR_ID_ALIAS0 && acceso_estructura <= (uint16_t)(HR_ID_ALIAS0 + 31)){
          uint16_t id_alias_temp = (uint16_t)(acceso_estructura - HR_ID_ALIAS0);
          out[i] = pack_word2(R.alias_buf, (uint8_t)id_alias_temp);
          break;
        }
        out[i] = 0; // reservas → 0
        break;
    }
  }
  return true;
}

// -----------------------------
// Escrituras (0x06 single)
// -----------------------------
/**
 * @brief Escribe un único registro holding (función Modbus 0x06)
 * 
 * Valida el rango de direcciones y los valores permitidos antes de realizar
 * la escritura. Registros de solo lectura y valores fuera de rango son rechazados.
 * 
 * @param addr Dirección del registro holding a escribir
 * @param value Valor de 16 bits a escribir en el registro
 * 
 * @return true si la escritura fue aceptada y el valor es válido
 * @return false si la escritura fue rechazada (registro R/O, valor fuera de rango, etc.)
 * 
 * @note Actualiza R.errors con DEV_ERR_RANGE si el valor está fuera de rango
 * @note Algunos registros marcan DEV_STATUS_CFG_DIRTY al escribirse
 * @note El alias debe escribirse con función 0x10 (escritura múltiple) para garantizar solvencia
 */
// 0x06 — Escritura single register (Holding). Valida rango/valor.
bool regs_write_holding(uint16_t addr, uint16_t value){
  switch(addr){
  case HR_CFG_BAUDIOS:
    // No se admite cambio de baudios en tiempo de ejecución (por compilación)
    // Rechaza escrituras: sólo lectura para informar del valor efectivo
    R.errors |= DEV_ERR_RANGE; return false;

  case HR_CFG_MPU_FILTRO_HZ:
    // Acepta rango típico codificado (ejemplo 5..98 Hz codificados); aquí laxamente <=200
      if (value<=200){ R.mpu_lpf_hz = value; R.status |= DEV_STATUS_CFG_DIRTY; return true; }
      R.errors |= DEV_ERR_RANGE; return false;

  case HR_CFG_ID_UNIDAD:
      if (value>=1 && value<=247){ R.unit_id = value; R.status |= DEV_STATUS_CFG_DIRTY; return true; }
      R.errors |= DEV_ERR_RANGE; return false;

  case HR_CFG_POLL_INTERVAL_MS: {
      // Acepta 10..5000 ms; 0 => aplica mínimo (10)
      uint16_t v = value;
      if (v < 10) v = 10;
      if (v > 5000) v = 5000;
      R.poll_interval_ms = v;
      return true;
    }

  case HR_CMD_IDENT_SEGUNDOS:
    R.ident_secs = value;  // la capa superior iniciará/parará el patrón BlinkIdent
    R.ident_write_seq++;   // marca evento de escritura (re-trigger incluso si valor igual)
      return true;

  case HR_CMD_GUARDAR:
    // Claves de control: 0xA55A=save-to-EEPROM
    // - 0xA55A: persistimos en EEPROM UnitID y Alias actuales y limpiamos CFG_DIRTY.

    if (value==0xA55A){
      EepromUtils::begin();
      if (R.unit_id >= 1 && R.unit_id <= 247){
        EepromUtils::writeUnitId(R.unit_id);
      }
      EepromUtils::writeAlias(R.alias_buf, R.alias_len);
      R.save = value;
      R.save_write_seq++;
      R.status &= ~DEV_STATUS_CFG_DIRTY;
      return true;
    }
    R.errors |= DEV_ERR_RANGE; return false;

    default:
      // R/O o fuera de rango
      // Alias debe escribirse de forma atómica con 0x10 empezando en HR_ID_ALIAS_LEN
      // Rechazar 0x06 sobre HR_ID_ALIAS_LEN o HR_ID_ALIAS0..31 para evitar alias parciales
      if (addr == HR_ID_ALIAS_LEN) { R.errors |= DEV_ERR_RANGE; return false; }
      if (addr >= HR_ID_ALIAS0 && addr <= (uint16_t)(HR_ID_ALIAS0 + 31)) { R.errors |= DEV_ERR_RANGE; return false; }
      R.errors |= DEV_ERR_RANGE;
      return false;
  }
}

/**
 * @brief Escribe múltiples registros holding consecutivos (función Modbus 0x10)
 * 
 * Implementa la escritura de bloques de registros. Tiene manejo especial para
 * el alias del dispositivo, que debe escribirse de forma atómica comenzando en
 * HR_ID_ALIAS_LEN. Para otros registros, delega a regs_write_holding().
 * 
 * @param addr Dirección inicial de los registros holding a escribir
 * @param count Número de registros consecutivos a escribir
 * @param values Puntero al array de valores a escribir (count elementos)
 * 
 * @return true si todas las escrituras fueron exitosas
 * @return false si alguna escritura falló o los parámetros son inválidos
 * 
 * @note Para el alias: values[0] = longitud (0..64), values[1..N] = datos ASCII empaquetados (2 bytes/registro)
 * @note La escritura del alias NO persiste en EEPROM aquí; se hace staging en RAM y se marca CFG_DIRTY.
 *       Use HR_CMD_GUARDAR = 0xA55A para guardar UnitID y Alias en EEPROM.
 * @note Para registros normales, itera llamando a regs_write_holding()
 */
// 0x10 — Escritura múltiple (bloques)
bool regs_write_multi(uint16_t addr, uint16_t count, const uint16_t* values){
  if(count==0 || !values) return false;
  
  // Caso especial: alias — escribir longitud + datos empaquetados
  if(addr == HR_ID_ALIAS_LEN){
    // 1) Longitud solicitada (capada a 64)
    uint16_t requested_len = values[0];
    if (requested_len > 64) requested_len = 64;

    // 2) Número de registros de datos aportados tras el de longitud
    const uint16_t data_regs = (count > 1) ? (uint16_t)(count - 1) : 0;
    //    Bytes realmente disponibles en el payload (2 bytes por registro)
    const uint16_t provided_bytes = (uint16_t)(data_regs * 2);
    // 3) Longitud efectiva a tomar: mínimo entre lo solicitado y lo aportado
    uint16_t effective_len = (requested_len < provided_bytes) ? requested_len : provided_bytes;

    // 4) Desempaquetar los bytes ASCII (MSB luego LSB) hasta effective_len
    char buf[65];
    uint16_t write_idx = 0;
    for (uint16_t r = 0; r < data_regs && write_idx < 64; ++r){
      const uint16_t word = values[1 + r];
      const uint8_t msb = (uint8_t)(word >> 8);
      const uint8_t lsb = (uint8_t)(word & 0xFF);

      if (write_idx < effective_len) buf[write_idx++] = (char)msb;
      if (write_idx < effective_len) buf[write_idx++] = (char)lsb;
    }

    // 5) Actualizar estado en RAM (staging). La persistencia se hará con 0xA55A
    R.alias_len = write_idx;          // por si llegan menos bytes de los solicitados
    memcpy(R.alias_buf, buf, R.alias_len);
    R.alias_buf[R.alias_len] = '\0';
    R.alias_loaded = true;            // Permite lectura inmediata del alias actualizado
    R.status |= DEV_STATUS_CFG_DIRTY; // Marcar pendiente de guardar
    return true;
  }
  // Por defecto: iterar escritura single
  for(uint16_t i=0;i<count;i++){
    if(!regs_write_holding((uint16_t)(addr + i), values[i])){//Solo se termina la iteracion con true si todos ok
      return false;
    }
  }
  return true;
}

/**
 * @brief Obtiene el contador de secuencia de escrituras en HR_CMD_IDENT_SEGUNDOS
 * 
 * Este contador se incrementa cada vez que se escribe en HR_CMD_IDENT_SEGUNDOS,
 * incluso si el valor escrito es el mismo. Permite detectar eventos de re-trigger
 * de identificación LED.
 * 
 * @return Valor actual del contador de secuencia de escrituras de identify
 */
// Exponer secuencia de escrituras de Identify
uint16_t regs_get_ident_write_seq(){
  return R.ident_write_seq;
}

// Exponer secuencia de escrituras de Save
uint16_t regs_get_save_write_seq(){
  return R.save_write_seq;
}

// -----------------------------
// Hooks de actualización desde otras capas
// -----------------------------
/**
 * @brief Actualiza los ángulos de inclinación medidos
 * 
 * @param ax Ángulo X en décimas de grado (mili-grados)
 * @param ay Ángulo Y en décimas de grado (mili-grados)
 * 
 * @note Marca el flag DEV_STATUS_MPU_READY en el estado del dispositivo
 */
void regs_set_angles_mdeg(int16_t ax, int16_t ay){ R.ang_x_mdeg = ax; R.ang_y_mdeg = ay; R.status |= DEV_STATUS_MPU_READY; }

/**
 * @brief Actualiza la temperatura medida
 * 
 * @param mc Temperatura en centésimas de grado Celsius (mili-°C)
 */
void regs_set_temp_mc(int16_t mc){ R.temp_mc = mc; }

/**
 * @brief Actualiza las medidas del acelerómetro
 * 
 * @param x Aceleración en eje X en mili-g
 * @param y Aceleración en eje Y en mili-g
 * @param z Aceleración en eje Z en mili-g
 */
void regs_set_acc_mg(int16_t x, int16_t y, int16_t z){ R.acc_x_mg=x; R.acc_y_mg=y; R.acc_z_mg=z; }

/**
 * @brief Actualiza las medidas del giroscopio
 * 
 * @param x Velocidad angular en eje X en mili-grados por segundo (mdps)
 * @param y Velocidad angular en eje Y en mili-grados por segundo (mdps)
 * @param z Velocidad angular en eje Z en mili-grados por segundo (mdps)
 */
void regs_set_gyr_mdps(int16_t x, int16_t y, int16_t z){ R.gyr_x_mdps=x; R.gyr_y_mdps=y; R.gyr_z_mdps=z; }

/**
 * @brief Actualiza la medida de peso/carga
 * 
 * @param kg_load Peso en kg (int16). Ej.: 12.34 kg -> 1234
 */
void regs_set_kg_load(int16_t kg_load){ R.load_kg = kg_load; }

/**
 * @brief Actualiza la velocidad y dirección del viento
 * 
 * @param speed_cmps Velocidad en cm/s (m/s * 100). Ej.: 3.45 m/s -> 345
 * @param dir_deg Dirección en grados 0-359 (0=Norte, 90=Este, 180=Sur, 270=Oeste)
 */
void regs_set_wind(uint16_t speed_cmps, uint16_t dir_deg) {
  R.wind_speed_cmps = speed_cmps;
  R.wind_dir_deg = (dir_deg >= 360) ? (dir_deg % 360) : dir_deg; // Normalizar 0-359
}

// Estadísticas: setters
void regs_set_wind_stats(uint16_t min_cmps, uint16_t max_cmps, uint16_t avg_cmps){
  R.wind_min_cmps = min_cmps;
  R.wind_max_cmps = max_cmps;
  R.wind_avg_cmps = avg_cmps;
}

void regs_set_accel_stats(int16_t x_max, int16_t x_min, int16_t x_avg,
                          int16_t y_max, int16_t y_min, int16_t y_avg,
                          int16_t z_max, int16_t z_min, int16_t z_avg){
  R.acc_x_max_mg = x_max; R.acc_x_min_mg = x_min; R.acc_x_avg_mg = x_avg;
  R.acc_y_max_mg = y_max; R.acc_y_min_mg = y_min; R.acc_y_avg_mg = y_avg;
  R.acc_z_max_mg = z_max; R.acc_z_min_mg = z_min; R.acc_z_avg_mg = z_avg;
}

/**
 * @brief Incrementa el contador de muestras
 * 
 * Debe llamarse cada vez que se adquiere una nueva muestra de datos del sensor.
 * El contador es de 32 bits y se expone como dos registros de 16 bits (LO/HI).
 */
void regs_bump_sample_counter(void){ R.sample_cnt++; }

// -----------------------------
// Diagnóstico y estado
// -----------------------------
/**
 * @brief Incrementa un contador de diagnóstico específico
 * 
 * @param reg_addr Dirección del registro de diagnóstico a incrementar
 *                 (HR_DIAG_TRAMAS_RX_OK, HR_DIAG_RX_CRC_ERROR, etc.)
 * 
 * @note Ignora direcciones que no corresponden a contadores de diagnóstico
 */
void regs_diag_inc(uint16_t reg_addr){
  switch(reg_addr){
    case HR_DIAG_TRAMAS_RX_OK:   R.rx_frames++;  break;
    case HR_DIAG_RX_CRC_ERROR:   R.rx_crc_err++; break;
    case HR_DIAG_RX_EXCEPCIONES: R.rx_excpt++;   break;
    case HR_DIAG_TRAMAS_TX_OK:   R.tx_frames++;  break;
    case HR_DIAG_DESBORDES_UART: R.overruns++;   break;
    default: break;
  }
}

/**
 * @brief Activa o desactiva flags de estado del dispositivo
 *      Se hace uso de un solo entero de 16 bits para gestionar todos los flags de estado.
 * @param mask Máscara de bits del flag de estado a modificar
 *             (DEV_STATUS_OK, DEV_STATUS_MPU_READY, DEV_STATUS_CFG_DIRTY, etc.)
 * @param enable true para activar el flag, false para desactivarlo
 * 
 * @note Los flags se exponen en el registro HR_INFO_ESTADO
 */
void regs_set_status(uint16_t mask, bool enable){
  if (enable) R.status |= mask; else R.status &= ~mask;
}

/**
 * @brief Activa o desactiva flags de error del dispositivo
 *    Se hace uso de un solo entero de 16 bits para gestionar todos los flags de error. 
 * @param mask Máscara de bits del flag de error a modificar
 *             (DEV_ERR_NONE, DEV_ERR_MPU, DEV_ERR_RANGE, DEV_ERR_COMM, etc.)
 * @param enable true para activar el flag de error, false para desactivarlo
 * 
 * @note Los flags se exponen en el registro HR_INFO_ERRORES
 */
void regs_set_error(uint16_t mask, bool enable){
  if (enable) R.errors |= mask; else R.errors &= ~mask;
}

// Getter de Unit ID actual
uint16_t regs_get_unit_id(){
  return R.unit_id;
}

uint16_t regs_get_cfg_poll_interval_ms(){
  return R.poll_interval_ms;
}

