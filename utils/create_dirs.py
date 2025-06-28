"""
Утилита для создания необходимых директорий
"""
import os
from pathlib import Path
from utils.logger import setup_logger

logger = setup_logger(__name__)


def create_required_directories():
    """Создать все необходимые директории"""
    directories = [
        "logs",
        "static",
        "static/charts",
        "static/images",
        "static/gifs"
    ]

    created_count = 0
    for directory in directories:
        dir_path = Path(directory)
        if not dir_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"✅ Created directory: {directory}")
            created_count += 1
        else:
            logger.debug(f"📁 Directory already exists: {directory}")

    if created_count > 0:
        logger.info(f"🎯 Created {created_count} new directories")
    else:
        logger.info("📁 All required directories already exist")

    return True


if __name__ == "__main__":
    create_required_directories()