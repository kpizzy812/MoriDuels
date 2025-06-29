#!/usr/bin/env python3
"""
Итоговая проверка готовности MORI Duels Bot
"""
import asyncio
import os
from pathlib import Path
from decimal import Decimal


async def check_database_connection():
    """Проверка подключения к БД"""
    try:
        from database.connection import async_session, init_db

        # Пробуем подключиться
        async with async_session() as session:
            from sqlalchemy import text
            result = await session.execute(text("SELECT 1"))
            result.fetchone()

        print("✅ База данных: Подключение OK")
        return True

    except Exception as e:
        print(f"❌ База данных: Ошибка подключения - {e}")
        return False


async def check_database_tables():
    """Проверка таблиц БД"""
    try:
        from database.connection import async_session
        from sqlalchemy import text

        required_tables = ['users', 'duels', 'transactions', 'rooms', 'wallet_history']

        async with async_session() as session:
            for table in required_tables:
                result = await session.execute(text(f"SELECT COUNT(*) FROM {table}"))
                count = result.scalar()
                print(f"✅ Таблица {table}: {count} записей")

        return True

    except Exception as e:
        print(f"❌ Таблицы БД: Ошибка - {e}")
        return False


async def check_solana_service():
    """Проверка Solana сервиса"""
    try:
        from services.solana_service import solana_service
        from config.settings import BOT_WALLET_ADDRESS, MORI_TOKEN_MINT

        if not BOT_WALLET_ADDRESS:
            print("❌ Solana: BOT_WALLET_ADDRESS не настроен")
            return False

        if not MORI_TOKEN_MINT:
            print("❌ Solana: MORI_TOKEN_MINT не настроен")
            return False

        # Проверяем подключение к RPC
        try:
            response = await solana_service.client.get_latest_blockhash()
            if response:
                print("✅ Solana RPC: Подключение OK")
            else:
                print("❌ Solana RPC: Нет ответа")
                return False
        except Exception as e:
            print(f"❌ Solana RPC: Ошибка - {e}")
            return False

        # Проверяем кошелек бота
        if solana_service.bot_keypair:
            print("✅ Solana: Приватный ключ бота загружен")
        else:
            print("❌ Solana: Приватный ключ бота не загружен")
            return False

        # Проверяем баланс SOL
        sol_balance = await solana_service.get_sol_balance(BOT_WALLET_ADDRESS)
        if sol_balance is not None:
            print(f"✅ Solana: SOL баланс бота: {sol_balance:.4f} SOL")
            if sol_balance < 0.01:
                print("⚠️  Solana: Низкий баланс SOL для газа!")
        else:
            print("❌ Solana: Не удалось получить баланс")
            return False

        # Проверяем MORI токен
        mint_info = await solana_service.validate_token_mint_info(MORI_TOKEN_MINT)
        if mint_info.get("valid"):
            print(f"✅ MORI токен: Валиден, decimals: {mint_info.get('decimals')}")
        else:
            print(f"❌ MORI токен: Невалиден - {mint_info.get('error')}")
            return False

        return True

    except Exception as e:
        print(f"❌ Solana сервис: Критическая ошибка - {e}")
        return False


async def check_telegram_bots():
    """Проверка телеграм ботов"""
    try:
        from config.settings import MAIN_BOT_TOKEN, TELEGRAM_API_ID, TELEGRAM_API_HASH

        # Проверяем основной бот
        if not MAIN_BOT_TOKEN or len(MAIN_BOT_TOKEN.split(':')) != 2:
            print("❌ Telegram: Неверный MAIN_BOT_TOKEN")
            return False

        print("✅ Telegram: MAIN_BOT_TOKEN настроен")

        # Проверяем user bot настройки
        if not TELEGRAM_API_ID or TELEGRAM_API_ID == 0:
            print("❌ Telegram: TELEGRAM_API_ID не настроен")
            return False

        if not TELEGRAM_API_HASH:
            print("❌ Telegram: TELEGRAM_API_HASH не настроен")
            return False

        print("✅ Telegram: User bot настройки OK")

        # Проверяем основной бот токен (пинг)
        import aiohttp
        async with aiohttp.ClientSession() as session:
            url = f"https://api.telegram.org/bot{MAIN_BOT_TOKEN}/getMe"
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("ok"):
                        bot_info = data["result"]
                        print(f"✅ Telegram: Бот @{bot_info['username']} активен")
                        return True
                    else:
                        print(f"❌ Telegram: Ошибка API - {data}")
                        return False
                else:
                    print(f"❌ Telegram: HTTP {response.status}")
                    return False

    except Exception as e:
        print(f"❌ Telegram боты: Ошибка - {e}")
        return False


async def check_admin_settings():
    """Проверка админских настроек"""
    try:
        from config.settings import ADMIN_IDS

        if not ADMIN_IDS:
            print("⚠️  Админы: ADMIN_IDS не настроен")
            return False

        print(f"✅ Админы: Настроено {len(ADMIN_IDS)} админов")
        return True

    except Exception as e:
        print(f"❌ Админы: Ошибка - {e}")
        return False


async def check_game_logic():
    """Проверка игровой логики"""
    try:
        from services.game_service import game_service

        # Проверяем что сервис инициализирован
        if hasattr(game_service, 'house_accounts') and game_service.house_accounts:
            print(f"✅ Игра: House аккаунты настроены ({len(game_service.house_accounts)})")
        else:
            print("⚠️  Игра: House аккаунты не настроены")

        # Проверяем настройки ставок
        from config.settings import MIN_BET, MAX_BET, HOUSE_COMMISSION

        if MIN_BET > 0 and MAX_BET > MIN_BET:
            print(f"✅ Игра: Ставки {MIN_BET}-{MAX_BET} MORI")
        else:
            print("❌ Игра: Неверные настройки ставок")
            return False

        if 0 < HOUSE_COMMISSION < 1:
            print(f"✅ Игра: Комиссия {HOUSE_COMMISSION * 100}%")
        else:
            print("❌ Игра: Неверная комиссия")
            return False

        return True

    except Exception as e:
        print(f"❌ Игровая логика: Ошибка - {e}")
        return False


async def check_monitoring():
    """Проверка мониторинга депозитов"""
    try:
        from services.deposit_monitor import deposit_monitor

        # Получаем статистику мониторинга
        stats = await deposit_monitor.get_monitoring_stats()

        if "error" not in stats:
            print("✅ Мониторинг: Сервис готов")
            print(f"   📊 Депозитов обработано: {stats.get('deposits_total', {}).get('count', 0)}")
            return True
        else:
            print(f"❌ Мониторинг: Ошибка - {stats['error']}")
            return False

    except Exception as e:
        print(f"❌ Мониторинг: Ошибка - {e}")
        return False


async def test_basic_flow():
    """Тест базового потока"""
    try:
        print("\n🧪 Тестирование основного потока:")

        # Тест создания пользователя
        from database.models.user import User

        test_user = await User.get_by_telegram_id(999999999)  # Тестовый ID
        if test_user:
            print("✅ Тест: Пользователь найден в БД")
        else:
            print("ℹ️  Тест: Тестовый пользователь не найден (это нормально)")

        # Тест валидации кошелька
        from services.solana_service import validate_solana_address
        from config.settings import BOT_WALLET_ADDRESS

        test_addresses = [
            "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM",  # Валидный
            "invalid_address",  # Невалидный
        ]

        if BOT_WALLET_ADDRESS:
            test_addresses.append(BOT_WALLET_ADDRESS)  # Кошелек бота

        for addr in test_addresses:
            is_valid = validate_solana_address(addr)
            status = "✅" if is_valid else "❌"
            print(f"{status} Валидация: {addr[:12]}... = {is_valid}")

        return True

    except Exception as e:
        print(f"❌ Тестирование: Ошибка - {e}")
        return False


def show_final_report(results):
    """Показать итоговый отчет"""
    print("\n" + "=" * 60)
    print("📋 ИТОГОВЫЙ ОТЧЕТ ГОТОВНОСТИ")
    print("=" * 60)

    passed = sum(results.values())
    total = len(results)
    percentage = (passed / total) * 100

    for check_name, passed in results.items():
        status = "✅" if passed else "❌"
        print(f"{status} {check_name}")

    print(f"\n📊 Готовность: {passed}/{total} ({percentage:.1f}%)")

    if percentage >= 90:
        print("\n🎉 БОТ ГОТОВ К ЗАПУСКУ!")
        print("🚀 Выполните: python main.py")
    elif percentage >= 70:
        print("\n⚠️  БОТ ЧАСТИЧНО ГОТОВ")
        print("🔧 Исправьте критические ошибки и повторите проверку")
    else:
        print("\n❌ БОТ НЕ ГОТОВ")
        print("🔧 Необходимо исправить множественные проблемы")

    print("\n💡 Минимально необходимо:")
    print("  ✅ База данных")
    print("  ✅ Telegram токен")
    print("  ✅ Solana RPC")
    print("  ✅ ADMIN_IDS")


async def main():
    """Основная проверка"""
    print("🔍 ИТОГОВАЯ ПРОВЕРКА ГОТОВНОСТИ MORI DUELS BOT")
    print("=" * 60)

    checks = {
        "База данных": await check_database_connection(),
        "Таблицы БД": await check_database_tables(),
        "Solana сервис": await check_solana_service(),
        "Telegram боты": await check_telegram_bots(),
        "Админские настройки": await check_admin_settings(),
        "Игровая логика": await check_game_logic(),
        "Мониторинг депозитов": await check_monitoring(),
        "Базовые тесты": await test_basic_flow()
    }

    show_final_report(checks)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Проверка прервана")
    except Exception as e:
        print(f"\n💥 Критическая ошибка проверки: {e}")