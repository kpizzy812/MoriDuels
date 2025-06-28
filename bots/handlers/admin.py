"""
Админ-панель для управления ботом
"""
from decimal import Decimal
from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

from database.models.user import User
from database.models.duel import Duel, DuelStatus
from database.models.transaction import Transaction, TransactionType, TransactionStatus
from services.game_service import game_service
from config.settings import ADMIN_IDS
from utils.logger import setup_logger

router = Router()
logger = setup_logger(__name__)


def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь админом"""
    return user_id in ADMIN_IDS


@router.message(Command("admin"))
async def admin_panel(message: Message):
    """Главная админ-панель"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к админ-панели!")
        return

    # Получаем статистику
    stats = await get_admin_stats()

    admin_text = f"""🛠 Админ-панель

📊 Общая статистика:
👥 Пользователей: {stats['users_count']}
🎮 Всего игр: {stats['total_games']}
💰 Общий оборот: {stats['total_volume']:,.0f} MORI
💼 Заработано комиссий: {stats['total_commission']:,.0f} MORI

📈 За последние 24ч:
🆕 Новых пользователей: {stats['new_users_24h']}
🎮 Игр: {stats['games_24h']}
💰 Оборот: {stats['volume_24h']:,.0f} MORI

🏠 House дуэли:
⚡ Активных: {stats['active_house_duels']}
📊 Всего сыграно: {stats['total_house_games']}"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users"),
            InlineKeyboardButton(text="🎮 Дуэли", callback_data="admin_duels")
        ],
        [
            InlineKeyboardButton(text="💰 Транзакции", callback_data="admin_transactions"),
            InlineKeyboardButton(text="🏠 House управление", callback_data="admin_house")
        ],
        [
            InlineKeyboardButton(text="📊 Детальная статистика", callback_data="admin_detailed_stats")
        ],
        [
            InlineKeyboardButton(text="⚙️ Настройки", callback_data="admin_settings")
        ]
    ])

    await message.answer(admin_text, reply_markup=keyboard)


@router.callback_query(F.data == "admin_users")
async def admin_users(callback: CallbackQuery):
    """Управление пользователями"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа!", show_alert=True)
        return

    # Получаем топ пользователей
    top_users = await get_top_users(limit=10)

    users_text = "👥 Топ пользователей:\n\n"

    for i, user in enumerate(top_users, 1):
        username = user.username if user.username else f"User {user.telegram_id}"
        users_text += f"{i}. @{username}\n"
        users_text += f"   💰 Баланс: {user.balance:,.0f} MORI\n"
        users_text += f"   🎮 Игр: {user.total_games} (🏆 {user.wins})\n"
        users_text += f"   📈 Прибыль: {user.get_profit():+,.0f} MORI\n\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔍 Поиск пользователя", callback_data="admin_search_user"),
            InlineKeyboardButton(text="📊 Статистика", callback_data="admin_user_stats")
        ],
        [
            InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")
        ]
    ])

    await callback.message.edit_text(users_text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "admin_duels")
async def admin_duels(callback: CallbackQuery):
    """Управление дуэлями"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа!", show_alert=True)
        return

    # Получаем активные дуэли
    active_duels = await get_active_duels()

    duels_text = "🎮 Активные дуэли:\n\n"

    if not active_duels:
        duels_text += "🔍 Нет активных дуэлей"
    else:
        for duel in active_duels[:10]:
            player1 = await User.get_by_telegram_id(duel.player1_id)
            player1_name = player1.username if player1 and player1.username else f"User {duel.player1_id}"

            if duel.is_house_duel:
                duels_text += f"🤖 Дуэль #{duel.id}\n"
                duels_text += f"   👤 @{player1_name} vs {duel.house_account_name}\n"
                duels_text += f"   💰 Ставка: {duel.stake:,.0f} MORI\n\n"
            else:
                player2 = await User.get_by_telegram_id(duel.player2_id) if duel.player2_id else None
                player2_name = player2.username if player2 and player2.username else f"User {duel.player2_id}"
                duels_text += f"👥 Дуэль #{duel.id}\n"
                duels_text += f"   👤 @{player1_name} vs @{player2_name}\n"
                duels_text += f"   💰 Ставка: {duel.stake:,.0f} MORI\n\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🏠 House дуэли", callback_data="admin_house_duels"),
            InlineKeyboardButton(text="📊 Статистика дуэлей", callback_data="admin_duel_stats")
        ],
        [
            InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")
        ]
    ])

    await callback.message.edit_text(duels_text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "admin_house_duels")
async def admin_house_duels(callback: CallbackQuery):
    """Управление House дуэлями"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа!", show_alert=True)
        return

    # Получаем активные house дуэли
    house_duels = await get_active_house_duels()

    if not house_duels:
        await callback.message.edit_text(
            "🏠 House дуэли\n\n🔍 Нет активных дуэлей с ботами",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_duels")]
            ])
        )
        await callback.answer()
        return

    duels_text = "🏠 Активные House дуэли:\n\n"
    keyboard_rows = []

    for duel in house_duels:
        player = await User.get_by_telegram_id(duel.player1_id)
        player_name = player.username if player and player.username else f"User {duel.player1_id}"

        duels_text += f"🎮 Дуэль #{duel.id}\n"
        duels_text += f"👤 @{player_name} vs {duel.house_account_name}\n"
        duels_text += f"💰 Ставка: {duel.stake:,.0f} MORI\n"

        # Добавляем кнопки управления
        keyboard_rows.append([
            InlineKeyboardButton(
                text=f"✅ #{duel.id} Игрок побеждает",
                callback_data=f"house_win_{duel.id}_true"
            ),
            InlineKeyboardButton(
                text=f"❌ #{duel.id} Игрок проигрывает",
                callback_data=f"house_win_{duel.id}_false"
            )
        ])
        duels_text += "\n"

    keyboard_rows.append([
        InlineKeyboardButton(text="🔙 Назад", callback_data="admin_duels")
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    await callback.message.edit_text(duels_text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("house_win_"))
async def admin_house_decision(callback: CallbackQuery):
    """Админ решение для House дуэли"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа!", show_alert=True)
        return

    try:
        parts = callback.data.split("_")
        duel_id = int(parts[2])
        player_wins = parts[3] == "true"

        # Выполняем бросок монеты с админским решением
        result = await game_service.flip_coin(duel_id, admin_decision=player_wins)

        if "error" in result:
            await callback.answer(f"❌ {result['error']}", show_alert=True)
            return

        # Уведомляем о результате
        outcome = "побеждает" if player_wins else "проигрывает"
        coin_result = "ОРЕЛ" if result["coin_result"] == "heads" else "РЕШКА"

        await callback.answer(
            f"✅ Дуэль #{duel_id} завершена!\nИгрок {outcome}\nВыпал: {coin_result}",
            show_alert=True
        )

        # Обновляем список дуэлей
        await admin_house_duels(callback)

        logger.info(f"✅ Admin decision for duel {duel_id}: player_wins={player_wins}")

    except Exception as e:
        logger.error(f"❌ Error in admin house decision: {e}")
        await callback.answer("❌ Ошибка обработки решения", show_alert=True)


@router.callback_query(F.data == "admin_transactions")
async def admin_transactions(callback: CallbackQuery):
    """Управление транзакциями"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа!", show_alert=True)
        return

    # Получаем последние транзакции
    recent_transactions = await get_recent_transactions(limit=10)
    pending_transactions = await Transaction.get_pending_transactions()

    trans_text = f"💰 Транзакции\n\n"
    trans_text += f"⏳ Ожидающих: {len(pending_transactions)}\n\n"

    if recent_transactions:
        trans_text += "📝 Последние 10 транзакций:\n\n"
        for tx in recent_transactions:
            user = await User.get_by_telegram_id(tx.user_id) if hasattr(tx, 'user_id') else None
            username = user.username if user and user.username else f"User {tx.user_id if hasattr(tx, 'user_id') else 'Unknown'}"

            status_emoji = {
                TransactionStatus.COMPLETED: "✅",
                TransactionStatus.PENDING: "⏳",
                TransactionStatus.FAILED: "❌",
                TransactionStatus.CANCELLED: "🚫"
            }.get(tx.status, "❓")

            trans_text += f"{status_emoji} {tx.get_display_type()}\n"
            trans_text += f"   👤 @{username}\n"
            trans_text += f"   💰 {tx.amount:+,.2f} MORI\n"
            trans_text += f"   📅 {tx.created_at.strftime('%d.%m %H:%M')}\n\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⏳ Ожидающие", callback_data="admin_pending_tx"),
            InlineKeyboardButton(text="❌ Неудачные", callback_data="admin_failed_tx")
        ],
        [
            InlineKeyboardButton(text="📊 Статистика", callback_data="admin_tx_stats")
        ],
        [
            InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")
        ]
    ])

    await callback.message.edit_text(trans_text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "admin_detailed_stats")
async def admin_detailed_stats(callback: CallbackQuery):
    """Детальная статистика"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа!", show_alert=True)
        return

    stats = await get_detailed_stats()

    stats_text = f"""📊 Детальная статистика

💰 Финансы:
• Общий баланс пользователей: {stats['total_user_balance']:,.0f} MORI
• Общий оборот: {stats['total_volume']:,.0f} MORI
• Заработано комиссий: {stats['total_commission']:,.0f} MORI
• Выплачено выигрышей: {stats['total_winnings']:,.0f} MORI

🎮 Игры:
• Всего дуэлей: {stats['total_duels']}
• House дуэлей: {stats['house_duels']} ({stats['house_percentage']:.1f}%)
• Реальных дуэлей: {stats['real_duels']} ({100 - stats['house_percentage']:.1f}%)
• Средняя ставка: {stats['avg_stake']:,.0f} MORI

👥 Пользователи:
• Всего: {stats['total_users']}
• Активных (играли): {stats['active_users']}
• Новых за неделю: {stats['new_users_week']}
• Средний баланс: {stats['avg_balance']:,.0f} MORI

📈 Активность:
• Игр в день: {stats['games_per_day']:.1f}
• Оборот в день: {stats['volume_per_day']:,.0f} MORI
• Комиссий в день: {stats['commission_per_day']:,.0f} MORI"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📈 График активности", callback_data="admin_activity_chart"),
            InlineKeyboardButton(text="💰 Финансовый отчет", callback_data="admin_financial_report")
        ],
        [
            InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")
        ]
    ])

    await callback.message.edit_text(stats_text, reply_markup=keyboard)
    await callback.answer()


# Вспомогательные функции для получения данных
async def get_admin_stats() -> dict:
    """Получить основную статистику для админки"""
    # В реальной реализации здесь были бы запросы к БД
    # Пока возвращаем заглушки
    return {
        'users_count': 127,
        'total_games': 1250,
        'total_volume': 125000,
        'total_commission': 37500,
        'new_users_24h': 5,
        'games_24h': 45,
        'volume_24h': 8500,
        'active_house_duels': 2,
        'total_house_games': 850
    }


async def get_top_users(limit: int = 10) -> list:
    """Получить топ пользователей"""
    # Заглушка - в реальности запрос к БД
    return []


async def get_active_duels() -> list:
    """Получить активные дуэли"""
    # Заглушка - в реальности запрос к БД
    return []


async def get_active_house_duels() -> list:
    """Получить активные House дуэли"""
    # Заглушка - в реальности запрос к БД
    return []


async def get_recent_transactions(limit: int = 10) -> list:
    """Получить последние транзакции"""
    # Заглушка - в реальности запрос к БД
    return []


async def get_detailed_stats() -> dict:
    """Получить детальную статистику"""
    # Заглушка - в реальности сложные запросы к БД
    return {
        'total_user_balance': 45000,
        'total_volume': 125000,
        'total_commission': 37500,
        'total_winnings': 87500,
        'total_duels': 1250,
        'house_duels': 850,
        'real_duels': 400,
        'house_percentage': 68.0,
        'avg_stake': 100,
        'total_users': 127,
        'active_users': 89,
        'new_users_week': 23,
        'avg_balance': 354,
        'games_per_day': 41.7,
        'volume_per_day': 4167,
        'commission_per_day': 1250
    }


@router.callback_query(F.data == "admin_panel")
async def back_to_admin_panel(callback: CallbackQuery):
    """Возврат в главное меню админки"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа!", show_alert=True)
        return

    # Повторно вызываем админ панель
    await admin_panel(callback.message)
