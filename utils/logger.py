import logging
import sys
from pathlib import Path
from config.settings import LOG_LEVEL

def setup_logger(name: str) -> logging.Logger:
    """Настройка логгера"""

    # Создаем папку для логов
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # Создаем логгер
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, LOG_LEVEL.upper()))

    # Если обработчики уже добавлены, не добавляем повторно
    if logger.handlers:
        return logger

    # Форматтер
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Обработчик для файла
    file_handler = logging.FileHandler(
        log_dir / "mori_duels.log", 
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)

    # Обработчик для консоли
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    # Добавляем обработчики
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
