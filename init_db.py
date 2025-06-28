#!/usr/bin/env python3
"""
Скрипт для инициализации базы данных
"""
import asyncio
import sys
from database.connection import init_db, close_db
from utils.logger import setup_logger

logger = setup_logger(__name__)


async def main():
    """Инициализация базы данных"""
    try:
        logger.info("🚀 Starting database initialization...")

        # Инициализируем базу данных
        await init_db()

        logger.info("✅ Database initialization completed successfully!")

        # Показываем созданные таблицы
        logger.info("📋 Created tables:")
        logger.info("  • users - Пользователи")
        logger.info("  • duels - Дуэли")
        logger.info("  • transactions - Транзакции")
        logger.info("  • rooms - Игровые комнаты")
        logger.info("  • wallet_history - История кошельков")

        print("\n✅ База данных успешно инициализирована!")
        print("🚀 Теперь можно запускать ботов: python main.py")

    except Exception as e:
        logger.error(f"❌ Error initializing database: {e}")
        print(f"\n❌ Ошибка инициализации базы данных: {e}")
        print("🔧 Проверьте настройки в .env файле")
        sys.exit(1)

    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())