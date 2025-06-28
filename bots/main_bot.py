"""
Основной бот для дуэлей MORI
"""
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config.settings import MAIN_BOT_TOKEN
from database.connection import init_db
from utils.logger import setup_logger

# Импорт handlers
from bots.handlers.start import router as start_router
from bots.handlers.wallet import router as wallet_router
from bots.handlers.balance import router as balance_router
from bots.handlers.game import router as game_router  # ← ДОБАВЛЕНО
from bots.handlers.rooms import router as rooms_router
from bots.handlers.admin import router as admin_router
from bots.handlers.stats import router as stats_router  # ← ДОБАВЛЕНО

logger = setup_logger(__name__)

# Создаем бота и диспетчер
bot = Bot(token=MAIN_BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


async def setup_bot():
    """Настройка бота"""
    logger.info("🔧 Setting up main bot...")

    # Инициализируем базу данных
    await init_db()

    # Регистрируем роутеры
    dp.include_router(start_router)
    dp.include_router(wallet_router)
    dp.include_router(balance_router)
    dp.include_router(game_router)  # ← ДОБАВЛЕНО
    dp.include_router(rooms_router)
    dp.include_router(stats_router)  # ← ДОБАВЛЕНО
    dp.include_router(admin_router)

    logger.info("✅ Main bot setup complete")


async def main_bot_polling():
    """Запуск основного бота"""
    try:
        await setup_bot()

        # Устанавливаем команды бота
        from aiogram.types import BotCommand
        await bot.set_my_commands([
            BotCommand(command="start", description="🚀 Начать игру"),
            BotCommand(command="balance", description="💰 Мой баланс"),
            BotCommand(command="stats", description="📊 Статистика"),
            BotCommand(command="help", description="❓ Помощь"),
        ])

        logger.info("🚀 Starting main bot polling...")
        await dp.start_polling(bot)

    except Exception as e:
        logger.error(f"❌ Error in main bot: {e}")
        raise
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main_bot_polling())