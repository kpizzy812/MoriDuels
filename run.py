#!/usr/bin/env python3
"""
Скрипт для удобного запуска MORI Duels Bot
"""
import asyncio
import sys
import os
from pathlib import Path

# Добавляем текущую директорию в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))

from utils.logger import setup_logger

logger = setup_logger(__name__)


def check_env_file():
    """Проверить наличие и заполненность .env файла"""
    env_path = Path(".env")

    if not env_path.exists():
        print("❌ Файл .env не найден!")
        print("📝 Скопируйте .env.example в .env и заполните все переменные")
        return False

    # Проверяем ключевые переменные
    required_vars = [
        "MAIN_BOT_TOKEN",
        "USER_BOT_TOKEN",
        "DATABASE_URL",
        "MORI_TOKEN_MINT",
        "BOT_WALLET_ADDRESS",
        "ADMIN_IDS"
    ]

    missing_vars = []
    with open(env_path, 'r') as f:
        env_content = f.read()

        for var in required_vars:
            if f"{var}=" not in env_content or f"{var}=your_" in env_content:
                missing_vars.append(var)

    if missing_vars:
        print("❌ Не заполнены обязательные переменные в .env:")
        for var in missing_vars:
            print(f"   • {var}")
        print("\n📝 Заполните все переменные и попробуйте снова")
        return False

    return True


def check_database():
    """Проверить подключение к базе данных"""
    try:
        import psycopg2
        from config.settings import DB_CONFIG

        conn = psycopg2.connect(**DB_CONFIG)
        conn.close()

        print("✅ Подключение к базе данных: OK")
        return True

    except ImportError:
        print("❌ psycopg2 не установлен: pip install psycopg2-binary")
        return False
    except Exception as e:
        print(f"❌ Ошибка подключения к БД: {e}")
        print("🔧 Проверьте настройки базы данных в .env")
        return False


async def init_database():
    """Инициализировать базу данных"""
    try:
        print("🔧 Инициализация базы данных...")

        from database.connection import init_db
        await init_db()

        print("✅ База данных инициализирована")
        return True

    except Exception as e:
        print(f"❌ Ошибка инициализации БД: {e}")
        return False


async def test_apis():
    """Проверить API подключения"""
    try:
        # Проверяем Solana RPC
        from services.solana_service import solana_service
        from config.settings import SOLANA_RPC_URL

        print(f"🔗 Проверка Solana RPC: {SOLANA_RPC_URL}")

        # Пытаемся получить последний блок
        response = await solana_service.client.get_latest_blockhash()
        if response:
            print("✅ Solana RPC: OK")
        else:
            print("⚠️ Solana RPC: Недоступен")

        # Проверяем Jupiter API
        from services.jupiter_service import jupiter_service
        print("🔗 Проверка Jupiter API...")

        # Тестовый запрос цены SOL
        sol_mint = "So11111111111111111111111111111111111111112"
        price_data = await jupiter_service.get_token_price(sol_mint)

        if price_data:
            print("✅ Jupiter API: OK")
        else:
            print("⚠️ Jupiter API: Недоступен (бот будет работать без цен)")

        return True

    except Exception as e:
        print(f"⚠️ Ошибка проверки API: {e}")
        return True  # Не критично для запуска


def show_startup_info():
    """Показать информацию при запуске"""
    print("\n" + "=" * 50)
    print("🪙 MORI Duels Bot")
    print("=" * 50)
    print("🎮 Telegram бот для дуэлей на MORI токенах")
    print("⛓️ Blockchain: Solana")
    print("💰 Токен: MORI")
    print("=" * 50 + "\n")


async def main():
    """Главная функция"""
    show_startup_info()

    # Проверки перед запуском
    print("🔍 Проверка конфигурации...")

    if not check_env_file():
        sys.exit(1)

    if not check_database():
        sys.exit(1)

    # Инициализация БД
    if not await init_database():
        sys.exit(1)

    # Проверка API
    await test_apis()

    print("\n🚀 Запуск ботов...\n")

    try:
        # Импортируем и запускаем main
        from main import main as run_bots
        await run_bots()

    except KeyboardInterrupt:
        print("\n🛑 Остановка ботов...")
        logger.info("Bot stopped by user")

    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        logger.error(f"Critical error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 До свидания!")