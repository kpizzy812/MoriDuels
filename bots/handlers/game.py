"""
Обработчики игровой логики
"""
from decimal import Decimal

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.models.user import User
from database.models.duel import Duel
from bots.keyboards.main_menu import get_main_menu, get_bet_amounts, get_coin_flip
from services.game_service import game_service
from config.settings import MIN_BET, MAX_BET
from utils.logger import setup_logger

router = Router()
logger = setup_logger(__name__)


class GameStates(StatesGroup):
    waiting_for_custom_bet = State()


@router.callback_query(F.data == "quick_game")
async def quick_game_menu(callback: CallbackQuery):
    """Меню быстрой игры"""
    user_id = callback.from_user.id
    user = await User.get_by_telegram_id(user_id)

    if not user:
        await callback.message.edit_text(
            """❌ Пользователь не найден!

Используйте /start для регистрации""",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]
            ])
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        f"""🎮 Быстрая игра

💰 Баланс: {user.balance:,.2f} MORI
🎯 Выберите ставку:

⚡ Система автоматически найдет оппонента
или создаст игру с ботом через 10 секунд""",
        reply_markup=get_bet_amounts()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("bet_"))
async def process_bet_selection(callback: CallbackQuery):
    """Обработка выбора ставки"""
    # Проверяем контекст (быстрая игра или создание комнаты)
    if callback.message.text and "Быстрая игра" not in callback.message.text:
        return  # Это обработчик комнат

    user_id = callback.from_user.id
    bet_data = callback.data.split("_")[1]

    if bet_data == "custom":
        # Запрашиваем пользовательскую ставку
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="quick_game")]
        ])

        await callback.message.edit_text(
            f"""✏️ Своя ставка

💰 Минимум: {MIN_BET:,.0f} MORI
📈 Максимум: {MAX_BET:,.0f} MORI

Введите сумму ставки:""",
            reply_markup=keyboard
        )

        # Устанавливаем состояние ожидания ставки
        from bots.main_bot import dp
        state = dp.fsm.get_context(bot=callback.bot, chat_id=callback.message.chat.id, user_id=user_id)
        await state.set_state(GameStates.waiting_for_custom_bet)
        await callback.answer()
        return

    try:
        stake = Decimal(bet_data)
    except:
        await callback.answer("❌ Ошибка обработки ставки", show_alert=True)
        return

    await start_quick_match(callback, user_id, stake)


@router.message(GameStates.waiting_for_custom_bet)
async def process_custom_bet(message: Message, state: FSMContext):
    """Обработка пользовательской ставки"""
    try:
        stake = Decimal(message.text.strip())

        if stake < MIN_BET:
            await message.answer(
                f"❌ Ставка слишком мала! Минимум: {MIN_BET:,.0f} MORI",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="quick_game")]
                ])
            )
            return

        if stake > MAX_BET:
            await message.answer(
                f"❌ Ставка слишком большая! Максимум: {MAX_BET:,.0f} MORI",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="quick_game")]
                ])
            )
            return

        # Создаем фиктивный callback
        class FakeCallback:
            def __init__(self, message):
                self.message = message
                self.from_user = message.from_user

            async def answer(self, text=None, show_alert=False):
                pass

        fake_callback = FakeCallback(message)
        await start_quick_match(fake_callback, message.from_user.id, stake)

    except ValueError:
        await message.answer(
            "❌ Введите корректное число!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="quick_game")]
            ])
        )
        return
    except Exception as e:
        logger.error(f"❌ Error processing custom bet: {e}")
        await message.answer("❌ Ошибка обработки ставки")

    await state.clear()


async def start_quick_match(callback, user_id: int, stake: Decimal):
    """Начать быстрый поиск игры"""
    try:
        user = await User.get_by_telegram_id(user_id)

        if not user or user.balance < stake:
            await callback.message.edit_text(
                "❌ Недостаточно средств!",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="💰 Пополнить", callback_data="deposit")],
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="quick_game")]
                ])
            )
            return

        # Показываем поиск игры
        await callback.message.edit_text(
            f"""🔍 Поиск игры...

💰 Ставка: {stake:,.0f} MORI
⏰ Ищем оппонента...

Подождите до 10 секунд""",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="quick_game")]
            ])
        )

        # Запускаем поиск
        result = await game_service.quick_match(user_id, stake)

        if "error" in result:
            await callback.message.edit_text(
                f"❌ {result['error']}",
                reply_markup=get_main_menu()
            )
            return

        # Успешно нашли игру
        if result["type"] == "real_duel":
            opponent_text = f"👤 Оппонент: @{result['opponent']}"
        else:
            opponent_text = f"🤖 Противник: {result['opponent']}"

        game_text = f"""✅ Игра найдена!

{opponent_text}
💰 Ставка: {stake:,.0f} MORI
🏆 Выигрыш: {stake * Decimal('1.7'):,.0f} MORI

Готовы бросить монету?"""

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎲 БРОСИТЬ МОНЕТУ", callback_data=f"flip_{result['duel_id']}")]
        ])

        await callback.message.edit_text(game_text, reply_markup=keyboard)

        logger.info(f"✅ Quick match found for user {user_id}: duel {result['duel_id']}")

    except Exception as e:
        logger.error(f"❌ Error in start_quick_match: {e}")
        await callback.message.edit_text(
            "❌ Ошибка поиска игры",
            reply_markup=get_main_menu()
        )


@router.callback_query(F.data.startswith("flip_"))
async def flip_coin(callback: CallbackQuery):
    """Бросок монеты"""
    try:
        duel_id = int(callback.data.split("_")[1])
        user_id = callback.from_user.id

        # Показываем анимацию броска
        await callback.message.edit_text(
            """🎲 Бросаем монету...

🪙 Монета в воздухе...
⏳ Ждите результат...""",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[])
        )

        # Ждем немного для эффекта
        import asyncio
        await asyncio.sleep(2)

        # Выполняем бросок
        result = await game_service.flip_coin(duel_id)

        if "error" in result:
            await callback.message.edit_text(
                f"❌ {result['error']}",
                reply_markup=get_main_menu()
            )
            await callback.answer()
            return

        # Определяем результат для пользователя
        player_won = (result["winner_id"] == user_id)
        coin_emoji = "🟡" if result["coin_result"] == "heads" else "⚪"
        coin_text = "ОРЕЛ" if result["coin_result"] == "heads" else "РЕШКА"

        if player_won:
            result_text = f"""🎉 ПОБЕДА! 🎉

{coin_emoji} Выпал: {coin_text}
🏆 Вы выиграли: {result['winner_amount']:,.2f} MORI

💰 Средства отправлены на ваш кошелек!"""

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎮 Играть еще", callback_data="quick_game")],
                [InlineKeyboardButton(text="📊 Баланс", callback_data="balance")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ])
        else:
            # Определяем противника
            if result["is_house_duel"]:
                opponent_name = result["house_account"]
            else:
                opponent_user = await User.get_by_telegram_id(result["winner_id"])
                opponent_name = f"@{opponent_user.username}" if opponent_user and opponent_user.username else f"Player {result['winner_id']}"

            result_text = f"""💔 Поражение

{coin_emoji} Выпал: {coin_text}
😔 Победил: {opponent_name}
💸 Потеряно: {result['winner_amount']:,.2f} MORI

Попробуйте еще раз!"""

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎮 Реванш", callback_data="quick_game")],
                [InlineKeyboardButton(text="💰 Пополнить", callback_data="deposit")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ])

        await callback.message.edit_text(result_text, reply_markup=keyboard)

        # Если это дуэль между игроками, уведомляем второго игрока
        if not result["is_house_duel"] and result["player2_id"] and result["player2_id"] != user_id:
            await notify_opponent(result["player2_id"], result, user_id)

        logger.info(f"✅ Coin flip completed for duel {duel_id}: {result['coin_result']}")

    except Exception as e:
        logger.error(f"❌ Error in flip_coin: {e}")
        await callback.message.edit_text(
            "❌ Ошибка при броске монеты",
            reply_markup=get_main_menu()
        )

    await callback.answer()


async def notify_opponent(opponent_id: int, result: dict, current_user_id: int):
    """Уведомить оппонента о результате"""
    try:
        from bots.main_bot import bot

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
😔 Вы проиграли
💸 Потеряно: {result['winner_amount']:,.2f} MORI"""

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎮 Играть еще", callback_data="quick_game")],
            [InlineKeyboardButton(text="📊 Статистика", callback_data="stats")]
        ])

        await bot.send_message(
            opponent_id,
            message_text,
            reply_markup=keyboard
        )

        logger.info(f"✅ Notified opponent {opponent_id} about duel result")

    except Exception as e:
        logger.error(f"❌ Error notifying opponent {opponent_id}: {e}")


@router.callback_query(F.data == "rules")
async def show_game_rules(callback: CallbackQuery):
    """Показать правила игры (дублирует stats.py, но для игрового контекста)"""
    await callback.message.edit_text(
        """ℹ️ Правила MORI Duels

🎮 Как играть:
1. Выберите размер ставки
2. Система найдет оппонента или создаст игру с ботом
3. Бросьте монету - орел или решка
4. Результат случаен (50/50)
5. Победитель получает 70% от общего банка

💰 Пример:
• Ваша ставка: 100 MORI
• Ставка оппонента: 100 MORI
• Общий банк: 200 MORI
• Комиссия (30%): 60 MORI
• Выигрыш: 140 MORI

🎯 Типы игр:
• 🎮 Быстрая игра - автоподбор
• 🏠 Комнаты - приватные игры
• 🤖 С ботами - когда нет игроков

🍀 Удачи в игре!""",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎮 Играть", callback_data="quick_game")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]
        ])
    )
    await callback.answer()