#!/usr/bin/env python3
"""
MORI Duels Bot - Главный файл запуска
"""
import asyncio
from bots.main_bot import main_bot_polling
from bots.user_bot import user_bot_polling
from utils.logger import setup_logger
from utils.create_dirs import create_required_directories

logger = setup_logger(__name__)


async def main():
    """Запуск всех ботов"""
    logger.info("🚀 Запуск MORI Duels Bot...")

    try:
        # Создаем необходимые папки
        create_required_directories()

        # Запускаем мониторинг депозитов
        from services.deposit_monitor import start_deposit_monitoring
        await start_deposit_monitoring()

        # Запускаем все компоненты параллельно
        await asyncio.gather(
            main_bot_polling(),
            user_bot_polling()
        )

    except KeyboardInterrupt:
        logger.info("🛑 Остановка ботов...")
        # Останавливаем мониторинг
        from services.deposit_monitor import stop_deposit_monitoring
        await stop_deposit_monitoring()
    except Exception as e:
        logger.error(f"❌ Ошибка запуска: {e}")


if __name__ == "__main__":
    asyncio.run(main())