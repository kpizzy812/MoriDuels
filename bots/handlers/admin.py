"""
Админ-панель для управления ботом
"""
from decimal import Decimal
from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.models.user import User
from database.models.duel import Duel, DuelStatus
from database.models.transaction import Transaction, TransactionType, TransactionStatus
from database.connection import async_session
from services.game_service import game_service
from config.settings import ADMIN_IDS, BOT_WALLET_ADDRESS, MORI_TOKEN_MINT
from utils.logger import setup_logger
from sqlalchemy import text
from typing import Optional

router = Router()
logger = setup_logger(__name__)

class AdminStates(StatesGroup):
    waiting_for_user_search = State()

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

    for i, user_data in enumerate(top_users, 1):
        username = user_data['username'] if user_data['username'] else f"User {user_data['telegram_id']}"
        users_text += f"{i}. @{username}\n"
        users_text += f"   💰 Баланс: {user_data['balance']:,.0f} MORI\n"
        users_text += f"   🎮 Игр: {user_data['total_games']} (🏆 {user_data['wins']})\n"
        users_text += f"   📈 Прибыль: {user_data['profit']:+,.0f} MORI\n\n"

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
            player1_name = duel['player1_username'] if duel['player1_username'] else f"User {duel['player1_id']}"

            if duel['is_house_duel']:
                duels_text += f"🤖 Дуэль #{duel['id']}\n"
                duels_text += f"   👤 @{player1_name} vs {duel['house_account_name']}\n"
                duels_text += f"   💰 Ставка: {duel['stake']:,.0f} MORI\n\n"
            else:
                player2_name = duel['player2_username'] if duel['player2_username'] else f"User {duel['player2_id']}"
                duels_text += f"👥 Дуэль #{duel['id']}\n"
                duels_text += f"   👤 @{player1_name} vs @{player2_name}\n"
                duels_text += f"   💰 Ставка: {duel['stake']:,.0f} MORI\n\n"

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
    house_duels = await game_service.get_active_house_duels()

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
    pending_count = await get_pending_transactions_count()

    trans_text = f"💰 Транзакции\n\n"
    trans_text += f"⏳ Ожидающих: {pending_count}\n\n"

    if recent_transactions:
        trans_text += "📝 Последние 10 транзакций:\n\n"
        for tx in recent_transactions:
            username = tx['username'] if tx['username'] else f"User {tx['user_id']}"

            status_emoji = {
                "completed": "✅",
                "pending": "⏳",
                "failed": "❌",
                "cancelled": "🚫"
            }.get(tx['status'], "❓")

            type_names = {
                "deposit": "💰 Пополнение",
                "withdrawal": "💸 Вывод",
                "duel_stake": "🎮 Ставка",
                "duel_win": "🏆 Выигрыш",
                "commission": "💼 Комиссия"
            }
            type_name = type_names.get(tx['type'], tx['type'])

            trans_text += f"{status_emoji} {type_name}\n"
            trans_text += f"   👤 @{username}\n"
            trans_text += f"   💰 {tx['amount']:+,.2f} MORI\n"
            trans_text += f"   📅 {tx['created_at'].strftime('%d.%m %H:%M')}\n\n"

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


# РЕАЛЬНЫЕ функции для получения данных из БД
async def get_admin_stats() -> dict:
    """Получить основную статистику для админки"""
    async with async_session() as session:
        try:
            # Общая статистика
            result = await session.execute(text("""
                SELECT 
                    (SELECT COUNT(*) FROM users) as users_count,
                    (SELECT COUNT(*) FROM duels WHERE status = 'finished'::duelstatus) as total_games,
                    (SELECT COALESCE(SUM(stake * 2), 0) FROM duels WHERE status = 'finished'::duelstatus) as total_volume,
                    (SELECT COALESCE(SUM(house_commission), 0) FROM duels WHERE status = 'finished'::duelstatus) as total_commission,
                    (SELECT COUNT(*) FROM users WHERE created_at >= NOW() - INTERVAL '24 hours') as new_users_24h,
                    (SELECT COUNT(*) FROM duels WHERE status = 'finished'::duelstatus AND finished_at >= NOW() - INTERVAL '24 hours') as games_24h,
                    (SELECT COALESCE(SUM(stake * 2), 0) FROM duels WHERE status = 'finished'::duelstatus AND finished_at >= NOW() - INTERVAL '24 hours') as volume_24h,
                    (SELECT COUNT(*) FROM duels WHERE status = 'active'::duelstatus AND is_house_duel = true) as active_house_duels,
                    (SELECT COUNT(*) FROM duels WHERE status = 'finished'::duelstatus AND is_house_duel = true) as total_house_games
            """))

            stats = result.fetchone()
            return {
                'users_count': stats.users_count,
                'total_games': stats.total_games,
                'total_volume': float(stats.total_volume),
                'total_commission': float(stats.total_commission),
                'new_users_24h': stats.new_users_24h,
                'games_24h': stats.games_24h,
                'volume_24h': float(stats.volume_24h),
                'active_house_duels': stats.active_house_duels,
                'total_house_games': stats.total_house_games
            }
        except Exception as e:
            logger.error(f"❌ Error getting admin stats: {e}")
            return {'users_count': 0, 'total_games': 0, 'total_volume': 0, 'total_commission': 0,
                   'new_users_24h': 0, 'games_24h': 0, 'volume_24h': 0, 'active_house_duels': 0, 'total_house_games': 0}


async def get_top_users(limit: int = 10) -> list:
    """Получить топ пользователей"""
    async with async_session() as session:
        try:
            result = await session.execute(text("""
                SELECT 
                    telegram_id, username, balance, total_games, wins,
                    (total_won - total_wagered) as profit
                FROM users 
                WHERE total_games > 0
                ORDER BY profit DESC, total_games DESC
                LIMIT :limit
            """), {"limit": limit})

            return [dict(row._mapping) for row in result.fetchall()]
        except Exception as e:
            logger.error(f"❌ Error getting top users: {e}")
            return []


async def get_active_duels() -> list:
    """Получить активные дуэли"""
    async with async_session() as session:
        try:
            result = await session.execute(text("""
                SELECT 
                    d.id, d.stake, d.is_house_duel, d.house_account_name,
                    d.player1_id, d.player2_id,
                    u1.username as player1_username,
                    u2.username as player2_username
                FROM duels d
                LEFT JOIN users u1 ON d.player1_id = u1.telegram_id
                LEFT JOIN users u2 ON d.player2_id = u2.telegram_id
                WHERE d.status = 'active'
                ORDER BY d.created_at DESC
            """))

            return [dict(row._mapping) for row in result.fetchall()]
        except Exception as e:
            logger.error(f"❌ Error getting active duels: {e}")
            return []


async def get_recent_transactions(limit: int = 10) -> list:
    """Получить последние транзакции"""
    async with async_session() as session:
        try:
            result = await session.execute(text("""
                SELECT 
                    t.type, t.amount, t.status, t.created_at,
                    u.username, u.telegram_id as user_id
                FROM transactions t
                LEFT JOIN users u ON t.user_id = u.id
                ORDER BY t.created_at DESC
                LIMIT :limit
            """), {"limit": limit})

            return [dict(row._mapping) for row in result.fetchall()]
        except Exception as e:
            logger.error(f"❌ Error getting recent transactions: {e}")
            return []


async def get_pending_transactions_count() -> int:
    """Получить количество ожидающих транзакций"""
    async with async_session() as session:
        try:
            result = await session.execute(text("""
                SELECT COUNT(*) FROM transactions WHERE status = 'pending'::transactionstatus
            """))
            return result.scalar()
        except Exception as e:
            logger.error(f"❌ Error getting pending transactions count: {e}")
            return 0


async def get_detailed_stats() -> dict:
    """Получить детальную статистику"""
    async with async_session() as session:
        try:
            result = await session.execute(text("""
                SELECT 
                    (SELECT COALESCE(SUM(balance), 0) FROM users) as total_user_balance,
                    (SELECT COALESCE(SUM(stake * 2), 0) FROM duels WHERE status = 'finished') as total_volume,
                    (SELECT COALESCE(SUM(house_commission), 0) FROM duels WHERE status = 'finished') as total_commission,
                    (SELECT COALESCE(SUM(winner_amount), 0) FROM duels WHERE status = 'finished' AND winner_amount IS NOT NULL) as total_winnings,
                    (SELECT COUNT(*) FROM duels WHERE status = 'finished') as total_duels,
                    (SELECT COUNT(*) FROM duels WHERE status = 'finished' AND is_house_duel = true) as house_duels,
                    (SELECT COUNT(*) FROM duels WHERE status = 'finished' AND is_house_duel = false) as real_duels,
                    (SELECT COALESCE(AVG(stake), 0) FROM duels WHERE status = 'finished') as avg_stake,
                    (SELECT COUNT(*) FROM users) as total_users,
                    (SELECT COUNT(*) FROM users WHERE total_games > 0) as active_users,
                    (SELECT COUNT(*) FROM users WHERE created_at >= NOW() - INTERVAL '7 days') as new_users_week,
                    (SELECT COALESCE(AVG(balance), 0) FROM users) as avg_balance
            """))

            stats = result.fetchone()

            # Рассчитываем дополнительные метрики
            house_percentage = (stats.house_duels / max(stats.total_duels, 1)) * 100
            games_per_day = stats.total_duels / max(1, 30)  # За последние 30 дней
            volume_per_day = float(stats.total_volume) / max(1, 30)
            commission_per_day = float(stats.total_commission) / max(1, 30)

            return {
                'total_user_balance': float(stats.total_user_balance),
                'total_volume': float(stats.total_volume),
                'total_commission': float(stats.total_commission),
                'total_winnings': float(stats.total_winnings),
                'total_duels': stats.total_duels,
                'house_duels': stats.house_duels,
                'real_duels': stats.real_duels,
                'house_percentage': house_percentage,
                'avg_stake': float(stats.avg_stake),
                'total_users': stats.total_users,
                'active_users': stats.active_users,
                'new_users_week': stats.new_users_week,
                'avg_balance': float(stats.avg_balance),
                'games_per_day': games_per_day,
                'volume_per_day': volume_per_day,
                'commission_per_day': commission_per_day
            }
        except Exception as e:
            logger.error(f"❌ Error getting detailed stats: {e}")
            return {'total_user_balance': 0, 'total_volume': 0, 'total_commission': 0, 'total_winnings': 0,
                   'total_duels': 0, 'house_duels': 0, 'real_duels': 0, 'house_percentage': 0, 'avg_stake': 0,
                   'total_users': 0, 'active_users': 0, 'new_users_week': 0, 'avg_balance': 0,
                   'games_per_day': 0, 'volume_per_day': 0, 'commission_per_day': 0}


@router.callback_query(F.data == "admin_settings")
async def admin_settings(callback: CallbackQuery):
    """Настройки системы"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа!", show_alert=True)
        return

    # Получаем статистику мониторинга
    from services.deposit_monitor import deposit_monitor
    monitor_stats = await deposit_monitor.get_monitoring_stats()

    settings_text = f"""⚙️ Настройки системы

🔍 Мониторинг депозитов:
• Статус: {"🟢 Активен" if monitor_stats.get("monitoring") else "🔴 Остановлен"}
• Последняя TX: {monitor_stats.get("last_signature", "Нет")}
• Кеш: {monitor_stats.get("processed_cache_size", 0)} транзакций

📊 Депозиты за 24ч:
• Количество: {monitor_stats.get("deposits_24h", {}).get("count", 0)}
• Сумма: {monitor_stats.get("deposits_24h", {}).get("sum", 0):,.0f} MORI

💰 Общие депозиты:
• Всего: {monitor_stats.get("deposits_total", {}).get("count", 0)}
• Сумма: {monitor_stats.get("deposits_total", {}).get("sum", 0):,.0f} MORI
• Ожидающих: {monitor_stats.get("deposits_total", {}).get("pending", 0)}

🔧 Версия бота: v1.0.0"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔄 Принудительная проверка", callback_data="admin_force_check"),
            InlineKeyboardButton(text="📊 Статистика Solana", callback_data="admin_solana_stats")
        ],
        [
            InlineKeyboardButton(text="🧹 Очистка expired rooms", callback_data="admin_cleanup_rooms")
        ],
        [
            InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")
        ]
    ])

    await callback.message.edit_text(settings_text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "admin_force_check")
async def admin_force_check(callback: CallbackQuery):
    """Принудительная проверка депозитов"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа!", show_alert=True)
        return

    await callback.answer("🔄 Запускаю принудительную проверку...", show_alert=True)

    try:
        from services.deposit_monitor import deposit_monitor
        result = await deposit_monitor.force_check_deposits()

        if result.get("success"):
            await callback.message.edit_text(
                "✅ Принудительная проверка завершена!\n\n"
                "Все новые депозиты обработаны.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_settings")]
                ])
            )
        else:
            await callback.message.edit_text(
                f"❌ Ошибка проверки:\n{result.get('error', 'Неизвестная ошибка')}",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_settings")]
                ])
            )

    except Exception as e:
        logger.error(f"❌ Error in force check: {e}")
        await callback.message.edit_text(
            f"❌ Ошибка при принудительной проверке: {e}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_settings")]
            ])
        )


@router.callback_query(F.data == "admin_cleanup_rooms")
async def admin_cleanup_rooms(callback: CallbackQuery):
    """Очистка истекших комнат"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа!", show_alert=True)
        return

    try:
        from database.models.room import Room
        cleaned_count = await Room.cleanup_expired_rooms()

        await callback.answer(f"🧹 Очищено комнат: {cleaned_count}", show_alert=True)

    except Exception as e:
        logger.error(f"❌ Error cleaning rooms: {e}")
        await callback.answer("❌ Ошибка очистки комнат", show_alert=True)


@router.callback_query(F.data == "admin_solana_stats")
async def admin_solana_stats(callback: CallbackQuery):
    """Статистика Solana"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа!", show_alert=True)
        return

    try:
        from services.solana_service import solana_service

        # Получаем баланс бота
        bot_sol_balance = await solana_service.get_sol_balance(BOT_WALLET_ADDRESS)
        bot_mori_balance = await solana_service.get_token_balance(BOT_WALLET_ADDRESS, MORI_TOKEN_MINT)

        # Проверяем валидность MORI mint
        mint_info = await solana_service.validate_token_mint_info(MORI_TOKEN_MINT)

        stats_text = f"""📊 Статистика Solana

🤖 Кошелек бота:
• Адрес: {BOT_WALLET_ADDRESS[:8]}...{BOT_WALLET_ADDRESS[-4:]}
• SOL баланс: {bot_sol_balance or 0:.4f} SOL
• MORI баланс: {bot_mori_balance or 0:,.2f} MORI

🪙 MORI токен:
• Mint: {MORI_TOKEN_MINT[:8]}...{MORI_TOKEN_MINT[-4:]}
• Валидность: {"✅ Валиден" if mint_info.get("valid") else "❌ Невалиден"}"""

        if mint_info.get("valid"):
            stats_text += f"""
• Decimals: {mint_info.get("decimals", "N/A")}
• Supply: {mint_info.get("supply_ui", 0):,.0f} MORI"""

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_settings")]
        ])

        await callback.message.edit_text(stats_text, reply_markup=keyboard)

    except Exception as e:
        logger.error(f"❌ Error getting Solana stats: {e}")
        await callback.message.edit_text(
            f"❌ Ошибка получения статистики Solana: {e}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_settings")]
            ])
        )

    await callback.answer()


@router.callback_query(F.data == "admin_search_user")
async def admin_search_user(callback: CallbackQuery, state: FSMContext):
    """Поиск пользователя"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа!", show_alert=True)
        return

    await callback.message.edit_text(
        """🔍 Поиск пользователя

Введите один из вариантов:
- Telegram ID (например: 123456789)
- Username (например: @username или username)
- Адрес кошелька Solana

🔎 Отправьте поисковый запрос:""",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_users")]
        ])
    )

    await state.set_state(AdminStates.waiting_for_user_search)
    await callback.answer()


@router.message(AdminStates.waiting_for_user_search)
async def process_user_search(message: Message, state: FSMContext):
    """Обработка поискового запроса пользователя"""
    if not is_admin(message.from_user.id):
        await state.clear()
        return

    search_query = message.text.strip()

    try:
        # Определяем тип поиска и ищем пользователя
        user = await search_user_by_query(search_query)

        if not user:
            await message.answer(
                f"❌ Пользователь не найден по запросу: `{search_query}`",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔍 Новый поиск", callback_data="admin_search_user")],
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_users")]
                ]),
                parse_mode="Markdown"
            )
            await state.clear()
            return

        # Показываем детальную информацию о пользователе
        user_info = await get_detailed_user_info(user)

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📊 Транзакции", callback_data=f"admin_user_txs_{user.id}"),
                InlineKeyboardButton(text="🎮 Дуэли", callback_data=f"admin_user_duels_{user.id}")
            ],
            [
                InlineKeyboardButton(text="💰 Изменить баланс", callback_data=f"admin_change_balance_{user.id}"),
                InlineKeyboardButton(text="🔒 Заблокировать", callback_data=f"admin_block_user_{user.id}")
            ],
            [
                InlineKeyboardButton(text="🔍 Новый поиск", callback_data="admin_search_user"),
                InlineKeyboardButton(text="🔙 Назад", callback_data="admin_users")
            ]
        ])

        await message.answer(user_info, reply_markup=keyboard, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"❌ Error searching user: {e}")
        await message.answer(
            "❌ Ошибка поиска пользователя",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_users")]
            ])
        )

    await state.clear()


async def search_user_by_query(query: str) -> Optional[User]:
    """Поиск пользователя по различным критериям"""
    try:
        # Убираем @ из username если есть
        if query.startswith('@'):
            query = query[1:]

        # Проверяем, является ли запрос числом (Telegram ID)
        if query.isdigit():
            telegram_id = int(query)
            return await User.get_by_telegram_id(telegram_id)

        # Проверяем, является ли запрос адресом кошелька (32-44 символа)
        if 32 <= len(query) <= 44:
            async with async_session() as session:
                result = await session.execute(
                    text("SELECT * FROM users WHERE wallet_address = :wallet"),
                    {"wallet": query}
                )
                row = result.fetchone()
                if row:
                    user = User()
                    for key, value in row._mapping.items():
                        setattr(user, key, value)
                    return user

        # Поиск по username
        async with async_session() as session:
            result = await session.execute(
                text("SELECT * FROM users WHERE LOWER(username) = LOWER(:username)"),
                {"username": query}
            )
            row = result.fetchone()
            if row:
                user = User()
                for key, value in row._mapping.items():
                    setattr(user, key, value)
                return user

        return None

    except Exception as e:
        logger.error(f"❌ Error in search_user_by_query: {e}")
        return None


async def get_detailed_user_info(user: User) -> str:
    """Получить детальную информацию о пользователе"""
    try:
        # Получаем дополнительную статистику
        async with async_session() as session:
            # Статистика транзакций
            tx_result = await session.execute(text("""
                SELECT 
                    COUNT(*) as total_txs,
                    COUNT(CASE WHEN type = 'deposit'::transactiontype THEN 1 END) as deposits,
                    COUNT(CASE WHEN type = 'withdrawal'::transactiontype THEN 1 END) as withdrawals,
                    COUNT(CASE WHEN status = 'pending'::transactionstatus THEN 1 END) as pending_txs,
                    COALESCE(SUM(CASE WHEN type = 'deposit'::transactiontype AND status = 'completed'::transactionstatus THEN amount ELSE 0 END), 0) as total_deposited,
                    COALESCE(SUM(CASE WHEN type = 'withdrawal'::transactiontype AND status = 'completed'::transactionstatus THEN amount ELSE 0 END), 0) as total_withdrawn
                FROM transactions 
                WHERE user_id = :user_id
            """), {"user_id": user.id})
            tx_stats = tx_result.fetchone()

            # Статистика дуэлей
            duels_result = await session.execute(text("""
                SELECT 
                    COUNT(*) as total_duels,
                    COUNT(CASE WHEN winner_id = :telegram_id THEN 1 END) as won_duels,
                    COUNT(CASE WHEN is_house_duel = true THEN 1 END) as house_duels,
                    COALESCE(AVG(stake), 0) as avg_stake,
                    COALESCE(MAX(stake), 0) as max_stake
                FROM duels 
                WHERE (player1_id = :telegram_id OR player2_id = :telegram_id) 
                AND status = 'finished'::duelstatus
            """), {"telegram_id": user.telegram_id})
            duels_stats = duels_result.fetchone()

        # Последняя активность
        last_activity = "Неизвестно"
        if tx_stats.total_txs > 0:
            last_tx_result = await session.execute(text("""
                SELECT created_at FROM transactions 
                WHERE user_id = :user_id 
                ORDER BY created_at DESC LIMIT 1
            """), {"user_id": user.id})
            last_tx = last_tx_result.fetchone()
            if last_tx:
                last_activity = last_tx.created_at.strftime('%d.%m.%Y %H:%M')

        # Формируем информацию
        status_emoji = "🟢" if user.is_active else "🔴"
        username_display = f"@{user.username}" if user.username else "Не установлен"

        info = f"""👤 Детальная информация о пользователе

{status_emoji} **Основные данные:**
- ID: `{user.telegram_id}`
- Username: {username_display}
- Статус: {"Активен" if user.is_active else "Заблокирован"}
- Регистрация: {user.created_at.strftime('%d.%m.%Y %H:%M')}
- Последняя активность: {last_activity}

💰 **Финансы:**
- Баланс: {user.balance:,.2f} MORI
- Всего внесено: {float(tx_stats.total_deposited):,.2f} MORI
- Всего выведено: {float(tx_stats.total_withdrawn):,.2f} MORI
- Прибыль: {user.get_profit():+,.2f} MORI

📊 **Транзакции:**
- Всего: {tx_stats.total_txs}
- Депозиты: {tx_stats.deposits}
- Выводы: {tx_stats.withdrawals}
- Ожидающих: {tx_stats.pending_txs}

🎮 **Игровая статистика:**
- Всего игр: {user.total_games}
- Побед: {user.wins} ({user.get_win_rate():.1f}%)
- Игр с ботами: {duels_stats.house_duels}
- Средняя ставка: {float(duels_stats.avg_stake):,.0f} MORI
- Максимальная ставка: {float(duels_stats.max_stake):,.0f} MORI

👛 **Кошелек:**
- Адрес: `{user.wallet_address[:16]}...{user.wallet_address[-8:]}`
- Обновлен: {user.wallet_updated_at.strftime('%d.%m.%Y %H:%M')}"""

        return info

    except Exception as e:
        logger.error(f"❌ Error getting detailed user info: {e}")
        return f"❌ Ошибка получения информации о пользователе: {e}"


@router.callback_query(F.data.startswith("admin_user_txs_"))
async def show_user_transactions(callback: CallbackQuery):
    """Показать транзакции пользователя"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа!", show_alert=True)
        return

    user_id = int(callback.data.split("_")[3])

    try:
        async with async_session() as session:
            result = await session.execute(text("""
                SELECT t.*, u.username, u.telegram_id
                FROM transactions t
                JOIN users u ON t.user_id = u.id
                WHERE t.user_id = :user_id
                ORDER BY t.created_at DESC
                LIMIT 20
            """), {"user_id": user_id})

            transactions = [dict(row._mapping) for row in result.fetchall()]

        if not transactions:
            tx_text = "📋 Транзакции пользователя\n\n❌ Транзакции не найдены"
        else:
            user_info = transactions[0]
            username = f"@{user_info['username']}" if user_info['username'] else f"User {user_info['telegram_id']}"

            tx_text = f"📋 Транзакции пользователя {username}\n\n"

            for tx in transactions:
                date_str = tx['created_at'].strftime('%d.%m %H:%M')
                status_emoji = {"completed": "✅", "pending": "⏳", "failed": "❌", "cancelled": "🚫"}.get(tx['status'],
                                                                                                       "❓")
                type_emoji = {"deposit": "💰", "withdrawal": "💸", "duel_stake": "🎮", "duel_win": "🏆",
                              "commission": "💼"}.get(tx['type'], "❓")

                tx_text += f"{status_emoji} {type_emoji} {tx['type'].upper()}\n"
                tx_text += f"   💰 {tx['amount']:+,.2f} MORI\n"
                tx_text += f"   📅 {date_str}\n"
                if tx['tx_hash']:
                    tx_text += f"   🔗 {tx['tx_hash'][:12]}...\n"
                tx_text += "\n"

        await callback.message.edit_text(
            tx_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад к пользователю", callback_data="admin_search_user")]
            ])
        )

    except Exception as e:
        logger.error(f"❌ Error showing user transactions: {e}")
        await callback.answer("❌ Ошибка загрузки транзакций", show_alert=True)

    await callback.answer()


@router.callback_query(F.data.startswith("admin_user_duels_"))
async def show_user_duels(callback: CallbackQuery):
    """Показать дуэли пользователя"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа!", show_alert=True)
        return

    user_id = int(callback.data.split("_")[3])

    try:
        async with async_session() as session:
            result = await session.execute(text("""
                SELECT d.*, u.telegram_id, u.username
                FROM duels d
                JOIN users u ON u.id = :user_id
                WHERE (d.player1_id = u.telegram_id OR d.player2_id = u.telegram_id)
                AND d.status = 'finished'::duelstatus
                ORDER BY d.finished_at DESC
                LIMIT 15
            """), {"user_id": user_id})

            duels = [dict(row._mapping) for row in result.fetchall()]

        if not duels:
            duels_text = "🎮 Дуэли пользователя\n\n❌ Дуэли не найдены"
        else:
            user_info = duels[0]
            username = f"@{user_info['username']}" if user_info['username'] else f"User {user_info['telegram_id']}"

            duels_text = f"🎮 Последние дуэли {username}\n\n"

            for duel in duels:
                date_str = duel['finished_at'].strftime('%d.%m %H:%M')
                won = (duel['winner_id'] == user_info['telegram_id'])
                result_emoji = "🏆" if won else "💔"
                coin_result = "ОРЕЛ" if duel['coin_result'] == 'heads' else "РЕШКА"

                duels_text += f"{result_emoji} Дуэль #{duel['id']}\n"
                duels_text += f"   💰 Ставка: {duel['stake']:,.0f} MORI\n"
                duels_text += f"   🪙 Выпал: {coin_result}\n"
                if won and duel['winner_amount']:
                    duels_text += f"   🎉 Выигрыш: {duel['winner_amount']:,.2f} MORI\n"
                duels_text += f"   📅 {date_str}\n\n"

        await callback.message.edit_text(
            duels_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад к пользователю", callback_data="admin_search_user")]
            ])
        )

    except Exception as e:
        logger.error(f"❌ Error showing user duels: {e}")
        await callback.answer("❌ Ошибка загрузки дуэлей", show_alert=True)

    await callback.answer()




@router.callback_query(F.data == "admin_pending_tx")
async def admin_pending_transactions(callback: CallbackQuery):
    """Ожидающие транзакции"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа!", show_alert=True)
        return

    try:
        # Получаем ожидающие транзакции
        pending_txs = await get_pending_transactions_details()

        if not pending_txs:
            await callback.message.edit_text(
                "💰 Ожидающие транзакции\n\n✅ Нет ожидающих транзакций",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_transactions")]
                ])
            )
            await callback.answer()
            return

        pending_text = f"⏳ Ожидающие транзакции ({len(pending_txs)}):\n\n"

        for tx in pending_txs[:10]:  # Показываем первые 10
            username = tx['username'] if tx['username'] else f"User {tx['user_id']}"

            type_names = {
                "deposit": "💰 Пополнение",
                "withdrawal": "💸 Вывод",
                "duel_stake": "🎮 Ставка",
                "duel_win": "🏆 Выигрыш"
            }
            type_name = type_names.get(tx['type'], tx['type'])

            pending_text += f"#{tx['id']} {type_name}\n"
            pending_text += f"   👤 @{username}\n"
            pending_text += f"   💰 {tx['amount']:,.2f} MORI\n"
            pending_text += f"   📅 {tx['created_at'].strftime('%d.%m %H:%M')}\n\n"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_pending_tx")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_transactions")]
        ])

        await callback.message.edit_text(pending_text, reply_markup=keyboard)

    except Exception as e:
        logger.error(f"❌ Error getting pending transactions: {e}")
        await callback.message.edit_text(
            "❌ Ошибка получения ожидающих транзакций",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_transactions")]
            ])
        )

    await callback.answer()


async def get_pending_transactions_details() -> list:
    """Получить детали ожидающих транзакций"""
    async with async_session() as session:
        try:
            result = await session.execute(text("""
                SELECT 
                    t.id, t.type, t.amount, t.created_at,
                    u.username, u.telegram_id as user_id
                FROM transactions t
                LEFT JOIN users u ON t.user_id = u.id
                WHERE t.status = 'pending'::transactionstatus
                ORDER BY t.created_at DESC
                LIMIT 20
            """))

            return [dict(row._mapping) for row in result.fetchall()]
        except Exception as e:
            logger.error(f"❌ Error getting pending transaction details: {e}")
            return []


@router.callback_query(F.data == "admin_panel")
async def back_to_admin_panel(callback: CallbackQuery):
    """Возврат в главное меню админки"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа!", show_alert=True)
        return

    # Повторно вызываем админ панель
    await admin_panel(callback.message)