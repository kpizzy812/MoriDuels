#!/usr/bin/env python3
"""
MORI Duels Bot - Главный файл запуска
"""
import asyncio
from bots.main_bot import main_bot_polling
from bots.user_bot import user_bot_polling
from utils.logger import setup_logger

logger = setup_logger(__name__)


async def main():
    """Запуск всех ботов"""
    logger.info("🚀 Запуск MORI Duels Bot...")

    try:
        # Запускаем оба бота параллельно
        await asyncio.gather(
            main_bot_polling(),
            user_bot_polling()
        )

    except KeyboardInterrupt:
        logger.info("🛑 Остановка ботов...")
    except Exception as e:
        logger.error(f"❌ Ошибка запуска: {e}")


if __name__ == "__main__":
    asyncio.run(main())