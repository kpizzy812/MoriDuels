#!/usr/bin/env python3
"""
Исправление настроек базы данных
"""
import os
import sys
from pathlib import Path


def check_current_settings():
    """Проверить текущие настройки"""
    print("🔍 Проверка текущих настроек...")

    env_path = Path(".env")
    if not env_path.exists():
        print("❌ Файл .env не найден!")
        return False

    with open(env_path, 'r') as f:
        content = f.read()

    # Ищем DATABASE_URL
    for line in content.split('\n'):
        if line.startswith('DATABASE_URL='):
            print(f"📋 Текущий DATABASE_URL: {line}")

            if 'username:password' in line:
                print("❌ В DATABASE_URL используются примерные данные!")
                return False
            elif 'sqlite' in line:
                print("✅ Используется SQLite")
                return True
            else:
                print("ℹ️  Используется PostgreSQL")
                return True

    print("❌ DATABASE_URL не найден в .env")
    return False


def fix_to_sqlite():
    """Переключить на SQLite"""
    print("\n🔧 Переключение на SQLite...")

    env_path = Path(".env")
    with open(env_path, 'r') as f:
        content = f.read()

    # Заменяем DATABASE_URL на SQLite
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if line.startswith('DATABASE_URL='):
            lines[i] = 'DATABASE_URL=sqlite+aiosqlite:///./mori_duels.db'
            break

    # Сохраняем
    with open(env_path, 'w') as f:
        f.write('\n'.join(lines))

    print("✅ DATABASE_URL обновлен на SQLite")

    # Проверяем aiosqlite
    try:
        import aiosqlite
        print("✅ aiosqlite уже установлен")
    except ImportError:
        print("📦 Устанавливаем aiosqlite...")
        import subprocess
        subprocess.run([sys.executable, "-m", "pip", "install", "aiosqlite"], check=True)
        print("✅ aiosqlite установлен")


def setup_postgresql():
    """Показать инструкции для PostgreSQL"""
    print("\n🐘 Настройка PostgreSQL:")
    print("1. Запустите PostgreSQL:")
    print("   sudo systemctl start postgresql  # Linux")
    print("   brew services start postgresql  # macOS")
    print()
    print("2. Создайте пользователя и БД:")
    print("   sudo -u postgres psql")
    print("   CREATE USER mori_user WITH PASSWORD 'secure_password_123';")
    print("   CREATE DATABASE mori_duels;")
    print("   GRANT ALL PRIVILEGES ON DATABASE mori_duels TO mori_user;")
    print("   \\q")
    print()
    print("3. Обновите .env:")
    print("   DATABASE_URL=postgresql+asyncpg://mori_user:secure_password_123@localhost:5432/mori_duels")


def check_telegram_token():
    """Проверить токен бота"""
    print("\n🤖 Проверка токена бота...")

    from dotenv import load_dotenv
    load_dotenv()

    bot_token = os.getenv('MAIN_BOT_TOKEN')

    if not bot_token:
        print("❌ MAIN_BOT_TOKEN не установлен!")
        return False
    elif bot_token.startswith('1234567890'):
        print("❌ MAIN_BOT_TOKEN содержит примерные данные!")
        print("📝 Получите реальный токен у @BotFather")
        return False
    elif ':' not in bot_token:
        print("❌ MAIN_BOT_TOKEN имеет неверный формат!")
        print("📝 Должен быть: 1234567890:ABCdefGHIjklMNO...")
        return False
    else:
        print("✅ MAIN_BOT_TOKEN выглядит корректно")
        return True


def main():
    """Основная функция"""
    print("🔧 ИСПРАВЛЕНИЕ НАСТРОЕК БАЗЫ ДАННЫХ")
    print("=" * 50)

    # Проверяем текущие настройки
    if check_current_settings():
        print("✅ Настройки базы данных выглядят корректно")
    else:
        print("\n❓ Выберите тип базы данных:")
        print("1. SQLite (рекомендуется для тестирования)")
        print("2. PostgreSQL (для продакшна)")

        choice = input("\nВаш выбор (1/2): ").strip()

        if choice == "1":
            fix_to_sqlite()
        elif choice == "2":
            setup_postgresql()
            print("\n⚠️  После настройки PostgreSQL перезапустите скрипт")
            return
        else:
            print("❌ Неверный выбор")
            return

    # Проверяем токен бота
    check_telegram_token()

    print("\n" + "=" * 50)
    print("🎯 Следующие шаги:")
    print("1. Если использовали SQLite - готово!")
    print("2. Если PostgreSQL - настройте его по инструкции выше")
    print("3. Обновите MAIN_BOT_TOKEN в .env (получите у @BotFather)")
    print("4. Запустите: python init_db.py")
    print()
    print("💡 Минимальные настройки для запуска:")
    print("   - DATABASE_URL (исправлен)")
    print("   - MAIN_BOT_TOKEN (нужен реальный)")
    print("   - ADMIN_IDS (ваш Telegram ID от @userinfobot)")


if __name__ == "__main__":
    main()