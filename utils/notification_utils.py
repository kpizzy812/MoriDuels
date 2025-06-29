"""
Безопасные функции для отправки уведомлений
"""
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup
from typing import Optional
from utils.logger import setup_logger

logger = setup_logger(__name__)


async def safe_send_message(
        bot: Bot,
        user_id: int,
        text: str,
        reply_markup: Optional[InlineKeyboardMarkup] = None,
        parse_mode: Optional[str] = None
) -> bool:
    """Безопасная отправка сообщения пользователю"""
    try:
        await bot.send_message(
            user_id,
            text,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )
        return True

    except TelegramForbiddenError:
        logger.warning(f"🚫 User {user_id} blocked the bot, skipping notification")
        return False

    except TelegramBadRequest as e:
        logger.warning(f"⚠️ Bad request for user {user_id}: {e}")
        return False

    except Exception as e:
        logger.error(f"❌ Error sending message to user {user_id}: {e}")
        return False


async def safe_edit_message(
        bot: Bot,
        user_id: int,
        message_id: int,
        text: str,
        reply_markup: Optional[InlineKeyboardMarkup] = None,
        parse_mode: Optional[str] = None
) -> bool:
    """Безопасное редактирование сообщения"""
    try:
        await bot.edit_message_text(
            text=text,
            chat_id=user_id,
            message_id=message_id,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )
        return True

    except TelegramForbiddenError:
        logger.warning(f"🚫 User {user_id} blocked the bot, skipping edit")
        return False

    except TelegramBadRequest as e:
        logger.warning(f"⚠️ Bad request for user {user_id}: {e}")
        return False

    except Exception as e:
        logger.error(f"❌ Error editing message for user {user_id}: {e}")
        return False


# Обновленная функция уведомления о депозите
async def safe_notify_user_about_deposit(bot: Bot, user, amount, tx_hash):
    """Безопасное уведомление пользователя о депозите"""
    try:
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

        message = f"""✅ Депозит зачислен!

💰 Сумма: {amount:,.2f} MORI
🔗 TX: {tx_hash[:12]}...
💳 Новый баланс: {user.balance:,.2f} MORI

Можете начинать играть! 🎮"""

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎮 Играть", callback_data="quick_game")],
            [InlineKeyboardButton(text="📊 Баланс", callback_data="balance")]
        ])

        success = await safe_send_message(
            bot,
            user.telegram_id,
            message,
            reply_markup=keyboard
        )

        if success:
            logger.info(f"📱 Notified user {user.telegram_id} about deposit")
        else:
            logger.warning(f"⚠️ Failed to notify user {user.telegram_id} about deposit")

    except Exception as e:
        logger.error(f"❌ Error in safe_notify_user_about_deposit: {e}")


# Обновленная функция уведомления оппонента
async def safe_notify_opponent(bot: Bot, opponent_id: int, result: dict, current_user_id: int):
    """Безопасное уведомление оппонента о результате"""
    try:
        from database.models.user import User
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

        opponent_won = (result["winner_id"] == opponent_id)
        coin_emoji = "🟡" if result["coin_result"] == "heads" else "⚪"
        coin_text = "ОРЕЛ" if result["coin_result"] == "heads" else "РЕШКА"

        current_user = await User.get_by_telegram_id(current_user_id)
        current_user_name = f"@{current_user.username}" if current_user and current_user.username else f"Player {current_user_id}"

        if opponent_won:
            message_text = f"""🎉 ПОБЕДА! 🎉

Дуэль с {current_user_name}:
{coin_emoji} Выпал: {coin_text}
🏆 Вы выиграли: {result['winner_amount']:,.2f} MORI

💰 Средства отправлены на ваш кошелек!"""
        else:
            message_text = f"""💔 Поражение

Дуэль с {current_user_name}:
{coin_emoji} Выпал: {coin_text}
😔 Вы проиграли свою ставку"""

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎮 Играть еще", callback_data="quick_game")],
            [InlineKeyboardButton(text="📊 Статистика", callback_data="stats")]
        ])

        success = await safe_send_message(
            bot,
            opponent_id,
            message_text,
            reply_markup=keyboard
        )

        if success:
            logger.info(f"✅ Notified opponent {opponent_id} about duel result")
        else:
            logger.warning(f"⚠️ Failed to notify opponent {opponent_id}")

    except Exception as e:
        logger.error(f"❌ Error notifying opponent {opponent_id}: {e}")