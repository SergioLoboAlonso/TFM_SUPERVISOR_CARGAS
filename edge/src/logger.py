"""
Logger configurado para el Edge Layer.
"""
import logging
import sys
from pathlib import Path
from config import Config

def setup_logger(name: str = 'edge') -> logging.Logger:
    """
    Configura el logger con formato y niveles.
    
    Args:
        name: Nombre del logger
        
    Returns:
        Logger configurado
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, Config.LOG_LEVEL))
    
    # Evitar duplicar handlers si ya están configurados
    if logger.handlers:
        return logger
    
    # Formato de log
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Handler para consola
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Handler para archivo (opcional)
    if Config.LOG_FILE:
        log_path = Path(__file__).parent.parent / Config.LOG_FILE
        file_handler = logging.FileHandler(log_path, mode='a', encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


# Logger global para el módulo
logger = setup_logger('edge')
