#!/usr/bin/env python3
"""
Скрипт проверки настроек проекта перед запуском
"""
import os
import sys
from pathlib import Path
import asyncio


def check_python_version():
    """Проверка версии Python"""
    if sys.version_info < (3, 9):
        print("❌ Требуется Python 3.9+")
        print(f"   Текущая версия: {sys.version}")
        return False
    else:
        print(f"✅ Python версия: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
        return True


def check_env_file():
    """Проверка .env файла"""
    env_path = Path(".env")
    if not env_path.exists():
        print("❌ Файл .env не найден!")
        print("   Создайте его: cp .env.example .env")
        return False

    print("✅ Файл .env найден")

    # Проверяем обязательные переменные
    from dotenv import load_dotenv
    load_dotenv()

    required_vars = {
        "MAIN_BOT_TOKEN": "Токен основного бота",
        "DATABASE_URL": "URL базы данных",
        "TELEGRAM_API_ID": "API ID для user bot",
        "TELEGRAM_API_HASH": "API Hash для user bot",
        "TELEGRAM_PHONE": "Номер телефона",
        "ADMIN_IDS": "ID администраторов"
    }

    missing_vars = []
    for var, description in required_vars.items():
        value = os.getenv(var)
        if not value or value.startswith('your_') or value == '0':
            missing_vars.append(f"{var} ({description})")
        else:
            print(f"✅ {var}: ****")

    if missing_vars:
        print("\n❌ Не заполнены обязательные переменные:")
        for var in missing_vars:
            print(f"   • {var}")
        return False

    return True


def check_dependencies():
    """Проверка установленных пакетов"""
    required_packages = [
        'aiogram', 'telethon', 'psycopg2', 'sqlalchemy',
        'matplotlib', 'pandas', 'numpy', 'aiohttp'
    ]

    missing_packages = []
    for package in required_packages:
        try:
            __import__(package)
            print(f"✅ {package}")
        except ImportError:
            missing_packages.append(package)
            print(f"❌ {package}")

    if missing_packages:
        print(f"\n❌ Не установлены пакеты: {', '.join(missing_packages)}")
        print("   Установите: pip install -r requirements.txt")
        return False

    return True


async def check_database():
    """Проверка подключения к базе данных"""
    try:
        from config.settings import DB_CONFIG
        import psycopg2

        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        cursor.close()
        conn.close()

        print(f"✅ PostgreSQL: {version[:20]}...")
        return True

    except ImportError:
        print("❌ psycopg2 не установлен")
        print("   Установите: pip install psycopg2-binary")
        return False
    except Exception as e:
        print(f"❌ Ошибка подключения к БД: {e}")
        print("   Проверьте настройки DATABASE_URL в .env")
        return False


def check_directories():
    """Проверка необходимых директорий"""
    required_dirs = [
        "logs", "static", "static/charts",
        "static/images", "bots/handlers"
    ]

    for directory in required_dirs:
        dir_path = Path(directory)
        if dir_path.exists():
            print(f"✅ {directory}/")
        else:
            print(f"⚠️  {directory}/ (будет создана)")

    return True


def check_telegram_settings():
    """Проверка настроек Telegram"""
    from config.settings import MAIN_BOT_TOKEN, TELEGRAM_API_ID, ADMIN_IDS

    # Проверка токена бота
    if not MAIN_BOT_TOKEN or len(MAIN_BOT_TOKEN.split(':')) != 2:
        print("❌ Неверный формат MAIN_BOT_TOKEN")
        print("   Должен быть: 1234567890:ABCdefGHIjklMNOpqrsTUVwxyz")
        return False

    # Проверка API_ID
    if not TELEGRAM_API_ID or TELEGRAM_API_ID == 0:
        print("❌ Неверный TELEGRAM_API_ID")
        print("   Получите на https://my.telegram.org")
        return False

    # Проверка ADMIN_IDS
    if not ADMIN_IDS:
        print("⚠️  ADMIN_IDS не настроен")
        print("   Получите свой ID у @userinfobot")
    else:
        print(f"✅ Админов настроено: {len(ADMIN_IDS)}")

    print("✅ Настройки Telegram выглядят корректно")
    return True


async def main():
    """Основная проверка"""
    print("🔍 ПРОВЕРКА НАСТРОЕК MORI DUELS BOT")
    print("=" * 50)

    checks = [
        ("Python версия", check_python_version),
        ("Файл .env", check_env_file),
        ("Python пакеты", check_dependencies),
        ("Папки проекта", check_directories),
        ("Настройки Telegram", check_telegram_settings),
        ("База данных", check_database),
    ]

    all_passed = True

    for check_name, check_func in checks:
        print(f"\n📋 {check_name}:")
        try:
            if asyncio.iscoroutinefunction(check_func):
                result = await check_func()
            else:
                result = check_func()

            if not result:
                all_passed = False
        except Exception as e:
            print(f"❌ Ошибка при проверке {check_name}: {e}")
            all_passed = False

    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ!")
        print("🚀 Можете запускать: python main.py")
    else:
        print("❌ ЕСТЬ ПРОБЛЕМЫ!")
        print("🔧 Исправьте ошибки выше и повторите проверку")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())