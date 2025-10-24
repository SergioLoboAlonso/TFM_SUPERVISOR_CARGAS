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

// -----------------------------
// Defaults de compilación
// -----------------------------
#ifndef UNIT_ID
  #define UNIT_ID 1
#endif
#ifndef FW_VER_MAJOR
  #define FW_VER_MAJOR 0x01
#endif
#ifndef FW_VER_MINOR
  #define FW_VER_MINOR 0x00
#endif
#ifndef HW_VER_MAJOR
  #define HW_VER_MAJOR 0x01
#endif
#ifndef HW_VER_MINOR
  #define HW_VER_MINOR 0x00
#endif

// -----------------------------
// Estado interno
// -----------------------------
static struct {
  // Info
  uint16_t vendor_id   = 0x5446;                 // 'T''F'
  uint16_t product_id  = 0x4D30;                 // 'M''0'
  uint16_t hw_version  = (HW_VER_MAJOR<<8) | HW_VER_MINOR;
  uint16_t fw_version  = (FW_VER_MAJOR<<8) | FW_VER_MINOR;
  uint16_t unit_id     = UNIT_ID;
  uint16_t caps        = (DEV_CAP_RS485|DEV_CAP_MPU6050|DEV_CAP_IDENT);
  uint16_t status      = DEV_STATUS_OK;
  uint16_t errors      = DEV_ERR_NONE;

  // Config
  uint16_t baud_code   = 4;                      // 115200
  uint16_t mpu_lpf_hz  = 42;                     // ejemplo codificado
  uint16_t save_apply  = 0;
  uint16_t ident_secs  = 0;

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
  uint32_t sample_cnt  = 0;

  // Diagnóstico
  uint16_t rx_frames   = 0;
  uint16_t rx_crc_err  = 0;
  uint16_t rx_excpt    = 0;
  uint16_t tx_frames   = 0;
  uint16_t overruns    = 0;
  uint16_t last_excpt  = 0;
} R;

// -----------------------------
// Helpers
// -----------------------------
static inline uint16_t uptime_lo() {
  return (uint16_t)((millis()/1000UL) & 0xFFFF);
}
static inline uint16_t uptime_hi() {
  return (uint16_t)(((millis()/1000UL) >> 16) & 0xFFFF);
}
static inline bool in_range(uint16_t addr, uint16_t min_a, uint16_t max_a, uint16_t count){
  if (addr < min_a) return false;
  if (addr > max_a) return false;
  if ((uint32_t)addr + count - 1 > max_a) return false;
  return true;
}

// -----------------------------
// Init
// -----------------------------
void regs_init(void){
  // Limpia estados transitorios si aplica
  R.status = (DEV_STATUS_OK);
  R.errors = DEV_ERR_NONE;
}

// -----------------------------
// Lecturas
// -----------------------------
bool regs_read_input(uint16_t addr, uint16_t count, uint16_t* out){
  if (count==0 || count>MAX_INPUT_READ) return false;
  if (!in_range(addr, IR_MIN_ADDR, IR_MAX_ADDR, count)) return false;

  for (uint16_t i=0;i<count;i++){
    uint16_t a = addr + i;
    switch(a){
  case IR_MED_ANGULO_X_CDEG:    out[i] = (uint16_t)R.ang_x_mdeg; break;
  case IR_MED_ANGULO_Y_CDEG:    out[i] = (uint16_t)R.ang_y_mdeg; break;
  case IR_MED_TEMPERATURA_CENTI:out[i] = (uint16_t)R.temp_mc;    break;
  case IR_MED_ACEL_X_mG:        out[i] = (uint16_t)R.acc_x_mg;   break;
  case IR_MED_ACEL_Y_mG:        out[i] = (uint16_t)R.acc_y_mg;   break;
  case IR_MED_ACEL_Z_mG:        out[i] = (uint16_t)R.acc_z_mg;   break;
  case IR_MED_GIRO_X_mdps:      out[i] = (uint16_t)R.gyr_x_mdps; break;
  case IR_MED_GIRO_Y_mdps:      out[i] = (uint16_t)R.gyr_y_mdps; break;
  case IR_MED_GIRO_Z_mdps:      out[i] = (uint16_t)R.gyr_z_mdps; break;
  case IR_MED_MUESTRAS_LO:      out[i] = (uint16_t)(R.sample_cnt & 0xFFFF); break;
  case IR_MED_MUESTRAS_HI:      out[i] = (uint16_t)((R.sample_cnt>>16) & 0xFFFF); break;
  case IR_MED_FLAGS_CALIDAD:     out[i] = 0; break; // placeholder de calidad
      default:                 out[i] = 0; break; // reservas → 0
    }
  }
  return true;
}
/**
 * @brief Reads holding registers from the Modbus device
 * 
 * This function reads a specified number of consecutive holding registers
 * starting from the given address and stores the values in the output buffer.
 * 
 * @param addr Starting address of the holding registers to read
 * @param count Number of consecutive holding registers to read
 * @param out Pointer to buffer where the read register values will be stored.
 *            Buffer must be large enough to hold 'count' uint16_t values.
 * 
 * @return true if the read operation was successful
 * @return false if the read operation failed (invalid address, communication error, etc.)
 * 
 * @note The caller is responsible for ensuring the output buffer has sufficient space
 * @note Address range and count validity should be verified before calling this function
 */
bool regs_read_holding(uint16_t addr, uint16_t count, uint16_t* out){
  if (count==0 || count>MAX_HOLDING_READ) return false;
  if (!in_range(addr, HR_MIN_ADDR, HR_MAX_ADDR, count)) return false;

  for (uint16_t i=0;i<count;i++){
    uint16_t a = addr + i;
    switch(a){
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
  case HR_CMD_GUARDAR_APLICAR: out[i] = R.save_apply; break; // eco último valor
  case HR_CMD_IDENT_SEGUNDOS:  out[i] = R.ident_secs; break; // eco último valor
  case HR_CFG_ID_UNIDAD:       out[i] = R.unit_id;    break;

      // Diagnóstico
  case HR_DIAG_TRAMAS_RX_OK:     out[i] = R.rx_frames;  break;
  case HR_DIAG_RX_CRC_ERROR:     out[i] = R.rx_crc_err; break;
  case HR_DIAG_RX_EXCEPCIONES:   out[i] = R.rx_excpt;   break;
  case HR_DIAG_TRAMAS_TX_OK:     out[i] = R.tx_frames;  break;
  case HR_DIAG_DESBORDES_UART:   out[i] = R.overruns;   break;
  case HR_DIAG_ULTIMA_EXCEPCION: out[i] = R.last_excpt; break;

      default: out[i] = 0; break;
    }
  }
  return true;
}

// -----------------------------
// Escrituras (0x06 single)
// -----------------------------
bool regs_write_holding(uint16_t addr, uint16_t value){
  switch(addr){
  case HR_CFG_BAUDIOS:
      if (value<=4){ R.baud_code = value; R.status |= DEV_STATUS_CFG_DIRTY; return true; }
      R.errors |= DEV_ERR_RANGE; return false;

  case HR_CFG_MPU_FILTRO_HZ:
      // acepta rango típico codificado (ejemplo 5..98 Hz codificados)
      if (value<=200){ R.mpu_lpf_hz = value; R.status |= DEV_STATUS_CFG_DIRTY; return true; }
      R.errors |= DEV_ERR_RANGE; return false;

  case HR_CFG_ID_UNIDAD:
      if (value>=1 && value<=247){ R.unit_id = value; R.status |= DEV_STATUS_CFG_DIRTY; return true; }
      R.errors |= DEV_ERR_RANGE; return false;

  case HR_CMD_IDENT_SEGUNDOS:
      R.ident_secs = value;  // la capa superior iniciará/parará el patrón
      return true;

  case HR_CMD_GUARDAR_APLICAR:
      // claves: 0xA55A=save, 0xB007=apply
      if (value==0xA55A || value==0xB007){ R.save_apply = value; return true; }
      R.errors |= DEV_ERR_RANGE; return false;

    default:
      // R/O o fuera de rango
      R.errors |= DEV_ERR_RANGE;
      return false;
  }
}

// -----------------------------
// Hooks de actualización desde otras capas
// -----------------------------
void regs_set_angles_mdeg(int16_t ax, int16_t ay){ R.ang_x_mdeg = ax; R.ang_y_mdeg = ay; R.status |= DEV_STATUS_MPU_READY; }
void regs_set_temp_mc(int16_t mc){ R.temp_mc = mc; }
void regs_set_acc_mg(int16_t x, int16_t y, int16_t z){ R.acc_x_mg=x; R.acc_y_mg=y; R.acc_z_mg=z; }
void regs_set_gyr_mdps(int16_t x, int16_t y, int16_t z){ R.gyr_x_mdps=x; R.gyr_y_mdps=y; R.gyr_z_mdps=z; }
void regs_bump_sample_counter(void){ R.sample_cnt++; }

// -----------------------------
// Diagnóstico y estado
// -----------------------------
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
void regs_set_status(uint16_t mask, bool enable){
  if (enable) R.status |= mask; else R.status &= ~mask;
}
void regs_set_error(uint16_t mask, bool enable){
  if (enable) R.errors |= mask; else R.errors &= ~mask;
}
