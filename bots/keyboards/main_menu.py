from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_main_menu() -> InlineKeyboardMarkup:
    """Главное меню бота"""
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
    """Выбор суммы ставки"""
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
    """Кнопка для броска монеты"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎲 БРОСИТЬ МОНЕТУ", callback_data="flip_coin")
        ]
    ])
