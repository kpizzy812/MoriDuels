# MORI Duels Bot

Телеграм бот для дуэлей на MORI токенах в Solana блокчейне.

## 🚀 Быстрый старт

```bash
# 1. Клонирование и установка
git clone <your-repo>
cd mori-duels-bot
python -m venv venv
source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt

# 2. Настройка
cp .env.example .env
# Заполните .env файл (см. инструкцию ниже)

# 3. Проверка настроек
python check_setup.py

# 4. Инициализация БД
python init_db.py

# 5. Запуск
python main.py
```

## 📖 Подробная документация

- **[ЗАПУСК_ПРОЕКТА.md](ЗАПУСК_ПРОЕКТА.md)** - Полная инструкция по установке
- **[SETUP_USERBOT.md](SETUP_USERBOT.md)** - Настройка user bot для графиков

## 🎮 Функции

- 🎲 **Дуэли "орел или решка"** на MORI токенах
- 🏠 **Система комнат** для приватных игр
- 💰 **Автоматические пополнения** и выводы
- 📊 **Красивые графики** цен в Telegram
- 👛 **Управление Solana кошельками**
- 🛠 **Админ-панель** для управления
- 🛡️ **Антиспам защита** для графиков

## ⚙️ Минимальные настройки .env

```bash
# Обязательно заполнить:
MAIN_BOT_TOKEN=ваш_токен_от_botfather
DATABASE_URL=postgresql://user:pass@localhost:5432/mori_duels
TELEGRAM_API_ID=ваш_api_id
TELEGRAM_API_HASH=ваш_api_hash  
TELEGRAM_PHONE=+ваш_номер
ADMIN_IDS=ваш_telegram_id
```

## 🔧 Требования

- **Python 3.9+**
- **PostgreSQL 13+**
- **Telegram аккаунт** (для user bot графиков)

## 📁 Структура проекта

```
├── bots/           # Telegram боты
│   ├── handlers/   # Обработчики команд
│   ├── keyboards/  # Инлайн клавиатуры
│   └── main_bot.py # Основной бот
├── database/       # Модели БД
├── services/       # Бизнес-логика
├── utils/          # Утилиты
├── static/         # Статические файлы
└── logs/           # Логи
```

## 🎯 Команды бота

**Основной бот:**
- `/start` - Начать игру
- `/balance` - Показать баланс
- `/stats` - Статистика игрока

**User bot (в чатах):**
- `/курс` - График + цена MORI
- `/график` - Только график

## 🐛 Решение проблем

**База данных не подключается:**
```bash
sudo systemctl start postgresql
python check_setup.py
```

**User bot не авторизуется:**
- Проверьте TELEGRAM_API_ID и API_HASH
- Убедитесь что номер в формате +1234567890

**Графики не генерируются:**
```bash
pip install matplotlib pandas numpy
mkdir -p static/charts
```

## 📊 Мониторинг

```bash
# Логи в реальном времени
tail -f logs/mori_duels.log

# Только ошибки
tail -f logs/mori_duels.log | grep ERROR
```

## 🔒 Безопасность

- ❌ Не делитесь файлами `.env` и `.session`
- ✅ Используйте сильные пароли для БД
- ✅ Регулярно делайте backup

## 📈 Статус разработки

**✅ Готово:**
- Основной бот с дуэлями
- User bot с графиками
- Система комнат
- База данных
- Админ-панель

**🔄 В разработке:**
- Реальные Solana транзакции
- Мониторинг депозитов
- Дополнительные игровые режимы

## 🤝 Поддержка

Если нужна помощь:
1. Проверьте логи: `tail -f logs/mori_duels.log`
2. Запустите диагностику: `python check_setup.py`
3. Создайте issue в GitHub

**Happy Gaming! 🎮✨**