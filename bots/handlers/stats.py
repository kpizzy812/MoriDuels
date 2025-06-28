"""
Обработчики статистики и правил
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

from database.models.user import User
from database.models.transaction import Transaction
from bots.keyboards.main_menu import get_main_menu
from utils.logger import setup_logger

router = Router()
logger = setup_logger(__name__)


@router.callback_query(F.data == "stats")
@router.message(Command("stats"))
async def show_user_stats(update):
    """Показать статистику пользователя"""
    # Определяем тип update (Message или CallbackQuery)
    if hasattr(update, 'from_user'):
        user_id = update.from_user.id
        edit_func = update.answer
    else:
        user_id = update.from_user.id
        edit_func = update.message.edit_text

    user = await User.get_by_telegram_id(user_id)

    if not user:
        await edit_func(
            """❌ Пользователь не найден!

Используйте /start для регистрации""",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]
            ])
        )
        if hasattr(update, 'answer'):
            await update.answer()
        return

    # Получаем дополнительную статистику
    recent_transactions = await Transaction.get_user_transactions(user.id, limit=5)

    # Считаем статистику по транзакциям
    total_deposits = sum(tx.amount for tx in recent_transactions if tx.type.value == "deposit")
    total_withdrawals = sum(tx.amount for tx in recent_transactions if tx.type.value == "withdrawal")

    stats_text = f"""📈 Ваша статистика

👤 Пользователь: {user.username or f'User {user.telegram_id}'}
📅 Регистрация: {user.created_at.strftime('%d.%m.%Y')}

💰 Финансы:
• Текущий баланс: {user.balance:,.2f} MORI
• Всего внесено: {total_deposits:,.2f} MORI
• Всего выведено: {total_withdrawals:,.2f} MORI

🎮 Игры:
• Игр сыграно: {user.total_games}
• Побед: {user.wins}
• Поражений: {user.total_games - user.wins}
• Процент побед: {user.get_win_rate():.1f}%

💎 Результат:
• Всего поставлено: {user.total_wagered:,.2f} MORI
• Всего выиграно: {user.total_won:,.2f} MORI
• Общая прибыль: {user.get_profit():+,.2f} MORI"""

    if user.total_games > 0:
        avg_stake = user.total_wagered / user.total_games
        stats_text += f"\n• Средняя ставка: {avg_stake:,.2f} MORI"

        if user.wins > 0:
            avg_win = user.total_won / user.wins
            stats_text += f"\n• Средний выигрыш: {avg_win:,.2f} MORI"

    # Определяем ранг игрока
    if user.get_win_rate() >= 70:
        rank = "🏆 Мастер"
    elif user.get_win_rate() >= 60:
        rank = "💎 Эксперт"
    elif user.get_win_rate() >= 50:
        rank = "⭐ Профи"
    elif user.total_games >= 10:
        rank = "🎮 Игрок"
    else:
        rank = "🌱 Новичок"

    stats_text += f"\n\n🏅 Ваш ранг: {rank}"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📋 История транзакций", callback_data="transaction_history"),
            InlineKeyboardButton(text="🏆 Рейтинг", callback_data="leaderboard")
        ],
        [
            InlineKeyboardButton(text="🎮 Играть", callback_data="quick_game"),
            InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")
        ]
    ])

    await edit_func(stats_text, reply_markup=keyboard)

    if hasattr(update, 'answer'):
        await update.answer()


@router.callback_query(F.data == "leaderboard")
async def show_leaderboard(callback: CallbackQuery):
    """Показать таблицу лидеров"""
    try:
        # В реальной реализации здесь был бы запрос к БД
        # Пока делаем заглушку
        leaderboard_text = """🏆 Таблица лидеров

👑 ТОП по прибыли:
1. 🥇 @crypto_king - +25,000 MORI
2. 🥈 @moon_trader - +18,500 MORI  
3. 🥉 @diamond_hands - +12,300 MORI
4. 🏅 @hodl_master - +9,800 MORI
5. 🏅 @lucky_player - +7,200 MORI

⭐ ТОП по проценту побед:
1. 🥇 @pro_gamer - 78.5% (89 игр)
2. 🥈 @coin_master - 76.2% (67 игр)
3. 🥉 @win_streak - 72.8% (103 игр)

🎮 ТОП по количеству игр:
1. 🥇 @game_addict - 234 игры
2. 🥈 @play_master - 198 игр
3. 🥉 @duel_king - 167 игр

💡 Играйте больше, чтобы попасть в рейтинг!"""

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📊 Моя статистика", callback_data="stats")
            ],
            [
                InlineKeyboardButton(text="🎮 Играть", callback_data="quick_game"),
                InlineKeyboardButton(text="🔙 Назад", callback_data="stats")
            ]
        ])

        await callback.message.edit_text(leaderboard_text, reply_markup=keyboard)
        await callback.answer()

    except Exception as e:
        logger.error(f"❌ Error showing leaderboard: {e}")
        await callback.answer("❌ Ошибка загрузки рейтинга", show_alert=True)


@router.callback_query(F.data == "rules")
@router.message(Command("rules"))
async def show_rules(update):
    """Показать правила игры"""
    # Определяем тип update
    if hasattr(update, 'from_user'):
        edit_func = update.answer
    else:
        edit_func = update.message.edit_text

    rules_text = """ℹ️ Правила MORI Duels

🎮 Как играть:
1. Пополните баланс MORI токенами
2. Выберите размер ставки
3. Найдите оппонента или играйте с ботом
4. Бросьте монету - орел или решка
5. Забирайте выигрыш!

💰 Выплаты:
• Выигрыш составляет 70% от ставки противника
• 30% остается как комиссия проекта
• Выигрыши отправляются на ваш кошелек

🎯 Типы игр:
• 🎮 Быстрая игра - автоподбор оппонента
• 🏠 Комнаты - создавайте приватные игры
• 🤖 С ботами - если нет реальных игроков

💸 Вывод средств:
• Комиссия за вывод: 5%
• Минимальная сумма: 10 MORI
• Средства поступают на ваш кошелек

⚠️ Важно:
• Игра основана на удаче (50/50)
• Играйте ответственно
• Не ставьте больше, чем можете потерять

🎲 Честность:
• Результат броска монеты случаен
• Система полностью прозрачна
• Все транзакции в блокчейне Solana"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎮 Начать игру", callback_data="quick_game"),
            InlineKeyboardButton(text="💰 Пополнить", callback_data="deposit")
        ],
        [
            InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")
        ]
    ])

    await edit_func(rules_text, reply_markup=keyboard)

    if hasattr(update, 'answer'):
        await update.answer()


@router.message(Command("help"))
async def help_command(message: Message):
    """Команда помощи"""
    help_text = """❓ Помощь MORI Duels

🚀 Основные команды:
/start - Начать работу с ботом
/balance - Показать баланс
/stats - Моя статистика  
/rules - Правила игры
/help - Эта справка

🎮 Игра:
• Нажмите "🎮 Быстрая игра" для поиска оппонента
• Или создайте комнату в разделе "🏠 Комнаты"
• Выберите ставку и бросьте монету!

💰 Управление балансом:
• "💰 Пополнить" - внести MORI токены
• "💸 Вывести" - вывести средства на кошелек
• "👛 Кошелек" - управление адресом

📊 Статистика:
• Отслеживайте свою прибыль
• Смотрите историю игр
• Сравнивайтесь с другими в рейтинге

🆘 Поддержка:
• Если возникли проблемы, обратитесь к @support
• Все транзакции логируются в блокчейне

🍀 Удачной игры!"""

    await message.answer(help_text, reply_markup=get_main_menu())


@router.message(Command("balance"))
async def balance_command(message: Message):
    """Быстрая команда для баланса"""
    user_id = message.from_user.id
    user = await User.get_by_telegram_id(user_id)

    if not user:
        await message.answer(
            "❌ Пользователь не найден! Используйте /start для регистрации"
        )
        return

    balance_text = f"""💰 Быстрый баланс

📊 Доступно: {user.balance:,.2f} MORI
🎮 Игр сыграно: {user.total_games}
🏆 Побед: {user.wins}
💎 Прибыль: {user.get_profit():+,.2f} MORI

Для подробной информации используйте кнопки ниже."""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Подробная статистика", callback_data="stats"),
            InlineKeyboardButton(text="💰 Управление балансом", callback_data="balance")
        ],
        [
            InlineKeyboardButton(text="🎮 Играть", callback_data="quick_game")
        ]
    ])

    await message.answer(balance_text, reply_markup=keyboard)