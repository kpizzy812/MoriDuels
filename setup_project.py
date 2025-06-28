#!/usr/bin/env python3
"""
Скрипт для создания структуры проекта MORI Duels Bot
"""
import os


def create_directory(path):
    """Создает директорию если её нет"""
    if not os.path.exists(path):
        os.makedirs(path)
        print(f"✅ Создана папка: {path}")
    else:
        print(f"📁 Папка уже существует: {path}")


def create_file(path, content=""):
    """Создает файл с содержимым"""
    if not os.path.exists(path):
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ Создан файл: {path}")
    else:
        print(f"📄 Файл уже существует: {path}")


def setup_project():
    """Основная функция создания структуры проекта"""

    print("🚀 Создание структуры проекта MORI Duels Bot...\n")

    # Создаем основные директории
    directories = [
        "bots",
        "bots/handlers",
        "bots/keyboards",
        "bots/middlewares",
        "database",
        "database/models",
        "services",
        "admin",
        "config",
        "utils",
        "logs",
        "static",
        "static/images",
        "static/gifs"
    ]

    for directory in directories:
        create_directory(directory)

    print("\n📁 Структура папок создана!\n")

    # Файлы конфигурации
    files_config = {
        ".env": """# Telegram Bot Tokens
MAIN_BOT_TOKEN=your_main_bot_token_here

# Telegram User Bot (получите на my.telegram.org)
TELEGRAM_API_ID=your_api_id_here
TELEGRAM_API_HASH=your_api_hash_here
TELEGRAM_PHONE=+1234567890

# Database
DATABASE_URL=postgresql://username:password@localhost:5432/mori_duels
DB_HOST=localhost
DB_PORT=5432
DB_NAME=mori_duels
DB_USER=username
DB_PASSWORD=password

# Solana
SOLANA_RPC_URL=https://api.mainnet-beta.solana.com
MORI_TOKEN_MINT=your_mori_token_mint_address
BOT_PRIVATE_KEY=your_bot_wallet_private_key
BOT_WALLET_ADDRESS=your_bot_wallet_address

# Jupiter API
JUPITER_API_KEY=your_jupiter_api_key
HELIUM_API_KEY=your_helium_api_key

# Birdeye API (для графиков)
BIRDEYE_API_KEY=your_birdeye_api_key_optional

# Admin Settings
ADMIN_IDS=123456789,987654321
CHANNEL_IDS=-1001234567890,-1001987654321

# House Accounts (for when no real players)
HOUSE_ACCOUNTS=@crypto_king,@moon_trader,@diamond_hands,@hodl_master

# Game Settings
MIN_BET=1
MAX_BET=100000
HOUSE_COMMISSION=0.30
WITHDRAWAL_COMMISSION=0.05
MATCH_TIMEOUT=10

# Logs
LOG_LEVEL=INFO
""",

        "requirements.txt": """# Telegram Bot
aiogram
aiofiles

# Database
psycopg2-binary
SQLAlchemy
alembic
asyncpg

# Solana
solders
solana
anchorpy

# Web3 & APIs  
requests
aiohttp
httpx

# Utils
python-dotenv
asyncio
Pillow
matplotlib
pandas

# Logging
loguru

# Date/Time
python-dateutil
pytz

# Validation
pydantic
""",

        "config/__init__.py": "",

        "config/settings.py": """import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
MAIN_BOT_TOKEN = os.getenv('MAIN_BOT_TOKEN')
USER_BOT_TOKEN = os.getenv('USER_BOT_TOKEN')
ADMIN_IDS = [int(x.strip()) for x in os.getenv('ADMIN_IDS', '').split(',') if x.strip()]
CHANNEL_IDS = [int(x.strip()) for x in os.getenv('CHANNEL_IDS', '').split(',') if x.strip()]

# Database
DATABASE_URL = os.getenv('DATABASE_URL')
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 5432)),
    'database': os.getenv('DB_NAME', 'mori_duels'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD')
}

# Solana
SOLANA_RPC_URL = os.getenv('SOLANA_RPC_URL')
MORI_TOKEN_MINT = os.getenv('MORI_TOKEN_MINT')
BOT_PRIVATE_KEY = os.getenv('BOT_PRIVATE_KEY')
BOT_WALLET_ADDRESS = os.getenv('BOT_WALLET_ADDRESS')

# APIs
JUPITER_API_KEY = os.getenv('JUPITER_API_KEY')
HELIUM_API_KEY = os.getenv('HELIUM_API_KEY')

# Game Settings
HOUSE_ACCOUNTS = [x.strip() for x in os.getenv('HOUSE_ACCOUNTS', '').split(',') if x.strip()]
MIN_BET = float(os.getenv('MIN_BET', 1))
MAX_BET = float(os.getenv('MAX_BET', 100000))
HOUSE_COMMISSION = float(os.getenv('HOUSE_COMMISSION', 0.30))
WITHDRAWAL_COMMISSION = float(os.getenv('WITHDRAWAL_COMMISSION', 0.05))
MATCH_TIMEOUT = int(os.getenv('MATCH_TIMEOUT', 10))

# Logging
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
""",

        "database/__init__.py": "",
        "database/models/__init__.py": "",
        "services/__init__.py": "",
        "admin/__init__.py": "",
        "utils/__init__.py": "",
        "bots/__init__.py": "",
        "bots/handlers/__init__.py": "",
        "bots/keyboards/__init__.py": "",
        "bots/middlewares/__init__.py": "",

        "main.py": """#!/usr/bin/env python3
\"\"\"
MORI Duels Bot - Главный файл запуска
\"\"\"
import asyncio
from bots.main_bot import main_bot_polling
from bots.user_bot import user_bot_polling
from utils.logger import setup_logger

logger = setup_logger(__name__)

async def main():
    \"\"\"Запуск всех ботов\"\"\"
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
""",

        "utils/logger.py": """import logging
import sys
from pathlib import Path
from config.settings import LOG_LEVEL

def setup_logger(name: str) -> logging.Logger:
    \"\"\"Настройка логгера\"\"\"

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
""",

        ".gitignore": """# Environment variables
.env
.env.local
.env.*.local

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# Virtual Environment
venv/
env/
ENV/
env.bak/
venv.bak/

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# Logs
logs/
*.log

# Database
*.db
*.sqlite3

# OS
.DS_Store
Thumbs.db

# Temporary files
*.tmp
*.temp

# Private keys
*.key
*.pem
""",

        "README.md": """# MORI Duels Bot

Телеграм бот для дуэлей на MORI токенах в Solana блокчейне.

## Функции

- 🎮 Дуэли "орел или решка" на MORI токенах
- 💰 Автоматические пополнения и выводы
- 🏠 Система комнат для игр
- 👛 Управление кошельками Solana
- 📊 Статистика игроков
- 🛠 Админ-панель

## Установка

1. Клонируйте репозиторий
2. Создайте виртуальное окружение: `python -m venv venv`
3. Активируйте: `source venv/bin/activate` (Linux/Mac) или `venv\\Scripts\\activate` (Windows)
4. Установите зависимости: `pip install -r requirements.txt`
5. Настройте `.env` файл
6. Запустите: `python main.py`

## Настройка

Скопируйте `.env` и заполните все необходимые переменные:

- Токены телеграм ботов
- Настройки базы данных PostgreSQL  
- Solana RPC и кошелек бота
- API ключи Jupiter/Helium
- ID администраторов и каналов

## Структура проекта

```
├── bots/           # Телеграм боты (aiogram)
│   ├── handlers/   # Обработчики команд
│   ├── keyboards/  # Инлайн клавиатуры
│   └── middlewares/# Промежуточное ПО
├── database/       # Модели базы данных
├── services/       # Бизнес-логика
├── admin/          # Админ-панель
├── config/         # Конфигурация
├── utils/          # Утилиты
├── logs/           # Логи
└── static/         # Статические файлы
```

## Запуск

```bash
python main.py
```

## Технологии

- **aiogram** - современный асинхронный фреймворк для Telegram ботов
- **PostgreSQL** - база данных
- **Solana/solders** - взаимодействие с блокчейном
- **SQLAlchemy** - ORM для работы с БД
- **Jupiter API** - получение цен токенов
""",

        "bots/keyboards/main_menu.py": """from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_main_menu() -> InlineKeyboardMarkup:
    \"\"\"Главное меню бота\"\"\"
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎮 Быстрая игра", callback_data="quick_game"),
            InlineKeyboardButton(text="🏠 Комнаты", callback_data="rooms")
        ],
        [
            InlineKeyboardButton(text="💰 Пополнить", callback_data="deposit"),
            InlineKeyboardButton(text="💸 Вывести", callback_data="withdraw")
        ],
        [
            InlineKeyboardButton(text="📊 Баланс", callback_data="balance"),
            InlineKeyboardButton(text="👛 Кошелек", callback_data="wallet")
        ],
        [
            InlineKeyboardButton(text="📈 Статистика", callback_data="stats"),
            InlineKeyboardButton(text="ℹ️ Правила", callback_data="rules")
        ]
    ])

def get_bet_amounts() -> InlineKeyboardMarkup:
    \"\"\"Выбор суммы ставки\"\"\"
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1 MORI", callback_data="bet_1"),
            InlineKeyboardButton(text="100 MORI", callback_data="bet_100"),
            InlineKeyboardButton(text="1000 MORI", callback_data="bet_1000")
        ],
        [
            InlineKeyboardButton(text="10K MORI", callback_data="bet_10000"),
            InlineKeyboardButton(text="50K MORI", callback_data="bet_50000")
        ],
        [
            InlineKeyboardButton(text="✏️ Своя сумма", callback_data="bet_custom")
        ],
        [
            InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")
        ]
    ])

def get_coin_flip() -> InlineKeyboardMarkup:
    \"\"\"Кнопка для броска монеты\"\"\"
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎲 БРОСИТЬ МОНЕТУ", callback_data="flip_coin")
        ]
    ])
""",

        "bots/handlers/start.py": """from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart

from bots.keyboards.main_menu import get_main_menu
from database.models.user import User
from utils.logger import setup_logger

router = Router()
logger = setup_logger(__name__)

@router.message(CommandStart())
async def cmd_start(message: Message):
    \"\"\"Обработчик команды /start\"\"\"
    user_id = message.from_user.id
    username = message.from_user.username

    # Проверяем, есть ли пользователь в БД
    user = await User.get_by_telegram_id(user_id)

    if not user:
        # Новый пользователь - нужно привязать кошелек
        await message.answer(
            \"\"\"Добро пожаловать в MORI Duels! 🪙

Для игры нужно привязать Solana кошелек
На него будут отправляться выигрыши

👛 Отправьте адрес своего кошелька:\"\"\"
        )
        return

    # Существующий пользователь
    balance = await user.get_balance()
    await message.answer(
        f\"\"\"Добро пожаловать в MORI Duels! 🪙

💰 Баланс: {balance:,.2f} MORI
👛 Кошелек: {user.wallet_address[:8]}...{user.wallet_address[-4:]}

Выберите действие:\"\"\",
        reply_markup=get_main_menu()
    )

@router.callback_query(F.data == "main_menu")
async def back_to_main_menu(callback: CallbackQuery):
    \"\"\"Возврат в главное меню\"\"\"
    await callback.message.edit_text(
        \"\"\"Добро пожаловать в MORI Duels! 🪙

Выберите действие:\"\"\",
        reply_markup=get_main_menu()
    )
    await callback.answer()
""",
    }

    # Создаем файлы
    for file_path, content in files_config.items():
        create_file(file_path, content)

    print("\n🎉 Проект успешно создан!")
    print("\n📋 Структура создана:")
    print("📁 bots/")
    print("  ├── handlers/     # Обработчики команд")
    print("  ├── keyboards/    # Инлайн клавиатуры")
    print("  └── middlewares/  # Промежуточное ПО")
    print("📁 database/        # Модели БД")
    print("📁 services/        # Solana, Jupiter, дуэли")
    print("📁 admin/           # Админ-панель")
    print("📁 static/gifs/     # Гифки для монеты")

    print("\n📋 Следующие шаги:")
    print("1. Установите зависимости: pip install -r requirements.txt")
    print("2. Настройте .env файл с вашими токенами")
    print("3. Создайте базу данных PostgreSQL")
    print("4. Запустите: python main.py")
    print("\n💡 Используем aiogram - современный асинхронный фреймворк!")
    print("💡 Зависимости без версий - меньше конфликтов!")


if __name__ == "__main__":
    setup_project()