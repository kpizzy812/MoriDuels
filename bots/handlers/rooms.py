"""
Обработчики для системы комнат
"""
from decimal import Decimal

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.models.user import User
from database.models.room import Room, RoomStatus
from bots.keyboards.main_menu import get_main_menu, get_bet_amounts
from config.settings import MIN_BET, MAX_BET
from utils.logger import setup_logger

router = Router()
logger = setup_logger(__name__)


class RoomStates(StatesGroup):
    waiting_for_room_stake = State()
    waiting_for_room_code = State()


@router.callback_query(F.data == "rooms")
async def rooms_menu(callback: CallbackQuery):
    """Главное меню комнат"""
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

    # Получаем активные комнаты
    await Room.cleanup_expired_rooms()  # Очищаем истекшие
    active_rooms = await Room.get_active_rooms(limit=10)

    rooms_text = f"""🏠 Игровые комнаты

💰 Баланс: {user.balance:,.2f} MORI

🎯 Активные комнаты:"""

    keyboard_rows = [
        [
            InlineKeyboardButton(text="➕ Создать комнату", callback_data="create_room"),
            InlineKeyboardButton(text="🔍 Найти по коду", callback_data="find_room")
        ]
    ]

    if active_rooms:
        rooms_text += "\n"
        for room in active_rooms[:5]:  # Показываем только первые 5
            creator = await User.get_by_telegram_id(room.creator_id)
            creator_name = creator.username if creator and creator.username else f"Player {room.creator_id}"
            time_left = room.get_time_left()
            minutes_left = int(time_left.total_seconds() // 60)

            rooms_text += f"\n💰 {room.stake:,.0f} MORI - @{creator_name}"
            rooms_text += f" ⏰ {minutes_left}м"

            # Добавляем кнопку присоединения
            keyboard_rows.append([
                InlineKeyboardButton(
                    text=f"🎮 Играть {room.stake:,.0f} MORI",
                    callback_data=f"join_room_{room.room_code}"
                )
            ])
    else:
        rooms_text += "\n\n🔍 Пока нет активных комнат\n➕ Создайте первую!"

    keyboard_rows.append([
        InlineKeyboardButton(text="🔄 Обновить", callback_data="rooms")
    ])
    keyboard_rows.append([
        InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    await callback.message.edit_text(rooms_text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "create_room")
async def create_room_menu(callback: CallbackQuery):
    """Меню создания комнаты"""
    user_id = callback.from_user.id
    user = await User.get_by_telegram_id(user_id)

    if not user:
        await callback.answer("❌ Пользователь не найден!", show_alert=True)
        return

    await callback.message.edit_text(
        f"""➕ Создать комнату

💰 Баланс: {user.balance:,.2f} MORI
🎯 Выберите ставку для комнаты:""",
        reply_markup=get_bet_amounts()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("bet_"))
async def process_room_bet_selection(callback: CallbackQuery):
    """Обработка выбора ставки для комнаты"""
    # Проверяем, что это запрос из создания комнаты
    if callback.message.text and "Создать комнату" not in callback.message.text:
        return  # Это не наш обработчик

    user_id = callback.from_user.id
    bet_data = callback.data.split("_")[1]

    if bet_data == "custom":
        # Запрашиваем пользовательскую ставку для комнаты
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="create_room")]
        ])

        await callback.message.edit_text(
            f"""✏️ Своя ставка для комнаты

💰 Минимум: {MIN_BET:,.0f} MORI
📈 Максимум: {MAX_BET:,.0f} MORI

Введите сумму ставки:""",
            reply_markup=keyboard
        )

        # Устанавливаем состояние ожидания ставки для комнаты
        from bots.main_bot import dp
        state = dp.fsm.get_context(bot=callback.bot, chat_id=callback.message.chat.id, user_id=user_id)
        await state.set_state(RoomStates.waiting_for_room_stake)
        await callback.answer()
        return

    try:
        stake = Decimal(bet_data)
    except:
        await callback.answer("❌ Ошибка обработки ставки", show_alert=True)
        return

    await create_room_with_stake(callback, user_id, stake)


@router.message(RoomStates.waiting_for_room_stake)
async def process_custom_room_stake(message: Message, state: FSMContext):
    """Обработка пользовательской ставки для комнаты"""
    try:
        stake = Decimal(message.text.strip())

        if stake < MIN_BET:
            await message.answer(
                f"❌ Ставка слишком мала! Минимум: {MIN_BET:,.0f} MORI",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="create_room")]
                ])
            )
            return

        if stake > MAX_BET:
            await message.answer(
                f"❌ Ставка слишком большая! Максимум: {MAX_BET:,.0f} MORI",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="create_room")]
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
        await create_room_with_stake(fake_callback, message.from_user.id, stake)

    except ValueError:
        await message.answer(
            "❌ Введите корректное число!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="create_room")]
            ])
        )
        return
    except Exception as e:
        logger.error(f"❌ Error processing custom room stake: {e}")
        await message.answer("❌ Ошибка обработки ставки")

    await state.clear()


async def create_room_with_stake(callback, user_id: int, stake: Decimal):
    """Создать комнату с указанной ставкой"""
    try:
        user = await User.get_by_telegram_id(user_id)

        if not user or user.balance < stake:
            await callback.message.edit_text(
                "❌ Недостаточно средств для создания комнаты!",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="💰 Пополнить", callback_data="deposit")],
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="rooms")]
                ])
            )
            return

        # Создаем комнату
        room = await Room.create_room(user_id, stake, expires_in_minutes=5)

        if not room:
            await callback.message.edit_text(
                "❌ Ошибка создания комнаты!",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="rooms")]
                ])
            )
            return

        # Генерируем ссылку для приглашения
        bot_username = "moriduels_bot"  # Нужно будет получить реальное имя бота
        share_link = room.get_share_link(bot_username)

        room_text = f"""✅ Комната создана!

🏠 Код комнаты: `{room.room_code}`
💰 Ставка: {stake:,.0f} MORI
⏰ Время ожидания: 5 минут
🔗 Ссылка: {share_link}

Ждем игрока... 👥"""

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📋 Копировать код", callback_data=f"copy_room_{room.room_code}"),
                InlineKeyboardButton(text="📤 Поделиться", url=share_link)
            ],
            [
                InlineKeyboardButton(text="❌ Закрыть комнату", callback_data=f"close_room_{room.room_code}")
            ],
            [
                InlineKeyboardButton(text="🏠 Все комнаты", callback_data="rooms")
            ]
        ])

        await callback.message.edit_text(
            room_text,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )

        logger.info(f"✅ Created room {room.room_code} by user {user_id} with stake {stake}")

    except Exception as e:
        logger.error(f"❌ Error creating room: {e}")
        await callback.message.edit_text(
            "❌ Ошибка создания комнаты",
            reply_markup=get_main_menu()
        )


@router.callback_query(F.data.startswith("copy_room_"))
async def copy_room_code(callback: CallbackQuery):
    """Копировать код комнаты"""
    room_code = callback.data.split("_")[2]
    await callback.answer(f"📋 Код скопирован: {room_code}", show_alert=True)


@router.callback_query(F.data.startswith("close_room_"))
async def close_room(callback: CallbackQuery):
    """Закрыть комнату"""
    room_code = callback.data.split("_")[2]
    user_id = callback.from_user.id

    try:
        room = await Room.get_by_code(room_code)

        if not room:
            await callback.answer("❌ Комната не найдена!", show_alert=True)
            return

        if room.creator_id != user_id:
            await callback.answer("❌ Вы не можете закрыть чужую комнату!", show_alert=True)
            return

        if room.status != RoomStatus.WAITING:
            await callback.answer("❌ Комната уже закрыта или заполнена!", show_alert=True)
            return

        # Закрываем комнату
        await room.close_room()

        await callback.message.edit_text(
            f"""❌ Комната закрыта

🏠 Код: {room_code}
💰 Ставка: {room.stake:,.0f} MORI

Комната была успешно закрыта.""",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏠 Все комнаты", callback_data="rooms")]
            ])
        )

        logger.info(f"✅ Closed room {room_code} by user {user_id}")

    except Exception as e:
        logger.error(f"❌ Error closing room {room_code}: {e}")
        await callback.answer("❌ Ошибка закрытия комнаты", show_alert=True)


@router.callback_query(F.data == "find_room")
async def find_room_menu(callback: CallbackQuery):
    """Меню поиска комнаты по коду"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="rooms")]
    ])

    await callback.message.edit_text(
        """🔍 Поиск комнаты

Введите код комнаты (6 символов):
Например: ABC123""",
        reply_markup=keyboard
    )

    # Устанавливаем состояние ожидания кода
    from bots.main_bot import dp
    state = dp.fsm.get_context(bot=callback.bot, chat_id=callback.message.chat.id, user_id=callback.from_user.id)
    await state.set_state(RoomStates.waiting_for_room_code)
    await callback.answer()


@router.message(RoomStates.waiting_for_room_code)
async def process_room_code(message: Message, state: FSMContext):
    """Обработка кода комнаты"""
    room_code = message.text.strip().upper()

    if len(room_code) != 6:
        await message.answer(
            "❌ Код комнаты должен содержать 6 символов!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="find_room")]
            ])
        )
        return

    try:
        room = await Room.get_by_code(room_code)

        if not room:
            await message.answer(
                f"❌ Комната {room_code} не найдена!",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔍 Найти другую", callback_data="find_room")],
                    [InlineKeyboardButton(text="🏠 Все комнаты", callback_data="rooms")]
                ])
            )
            await state.clear()
            return

        if room.status != RoomStatus.WAITING:
            status_text = {
                RoomStatus.FULL: "заполнена",
                RoomStatus.EXPIRED: "истекла",
                RoomStatus.CLOSED: "закрыта"
            }.get(room.status, "недоступна")

            await message.answer(
                f"❌ Комната {room_code} {status_text}!",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🏠 Все комнаты", callback_data="rooms")]
                ])
            )
            await state.clear()
            return

        if room.is_expired():
            await room.expire_room()
            await message.answer(
                f"❌ Комната {room_code} истекла!",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🏠 Все комнаты", callback_data="rooms")]
                ])
            )
            await state.clear()
            return

        # Показываем информацию о комнате
        creator = await User.get_by_telegram_id(room.creator_id)
        creator_name = creator.username if creator and creator.username else f"Player {room.creator_id}"
        time_left = room.get_time_left()
        minutes_left = int(time_left.total_seconds() // 60)

        room_info = f"""🏠 Комната {room_code}

👤 Создатель: @{creator_name}
💰 Ставка: {room.stake:,.0f} MORI
⏰ Осталось: {minutes_left} мин

Присоединиться к игре?"""

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🎮 Присоединиться", callback_data=f"join_room_{room_code}")
            ],
            [
                InlineKeyboardButton(text="🏠 Все комнаты", callback_data="rooms")
            ]
        ])

        await message.answer(room_info, reply_markup=keyboard)

    except Exception as e:
        logger.error(f"❌ Error processing room code {room_code}: {e}")
        await message.answer("❌ Ошибка поиска комнаты")

    await state.clear()


@router.callback_query(F.data.startswith("join_room_"))
async def join_room(callback: CallbackQuery):
    """Присоединиться к комнате"""
    room_code = callback.data.split("_")[2]
    user_id = callback.from_user.id

    try:
        room = await Room.get_by_code(room_code)

        if not room:
            await callback.answer("❌ Комната не найдена!", show_alert=True)
            return

        if room.creator_id == user_id:
            await callback.answer("❌ Вы не можете присоединиться к своей комнате!", show_alert=True)
            return

        user = await User.get_by_telegram_id(user_id)
        if not user or user.balance < room.stake:
            await callback.message.edit_text(
                f"""❌ Недостаточно средств!

🏠 Комната: {room_code}
💰 Требуется: {room.stake:,.0f} MORI
📊 У вас: {user.balance if user else 0:,.0f} MORI""",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="💰 Пополнить", callback_data="deposit")],
                    [InlineKeyboardButton(text="🏠 Все комнаты", callback_data="rooms")]
                ])
            )
            await callback.answer()
            return

        # Снимаем ставку с баланса
        if not await user.subtract_balance(room.stake):
            await callback.answer("❌ Ошибка списания средств!", show_alert=True)
            return

        # Присоединяемся к комнате
        duel = await room.join_room(user_id)

        if not duel:
            # Возвращаем деньги
            await user.add_balance(room.stake)
            await callback.answer("❌ Не удалось присоединиться к комнате!", show_alert=True)
            return

        # Успешно присоединились
        creator = await User.get_by_telegram_id(room.creator_id)
        creator_name = creator.username if creator and creator.username else f"Player {room.creator_id}"

        success_text = f"""✅ Присоединились к комнате!

🎮 Дуэль с @{creator_name}
💰 Ставка: {room.stake:,.0f} MORI
🏆 Выигрыш: {room.stake * Decimal('1.7'):,.0f} MORI

Готовы бросить монету?"""

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎲 БРОСИТЬ МОНЕТУ", callback_data=f"flip_{duel.id}")]
        ])

        await callback.message.edit_text(success_text, reply_markup=keyboard)

        # Уведомляем создателя комнаты
        try:
            from bots.main_bot import bot
            joiner_name = user.username if user.username else f"Player {user_id}"
            await bot.send_message(
                room.creator_id,
                f"""🎮 К вашей комнате присоединился игрок!

👤 Игрок: @{joiner_name}
🏠 Комната: {room_code}
💰 Ставка: {room.stake:,.0f} MORI

Дуэль начинается!""",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🎲 БРОСИТЬ МОНЕТУ", callback_data=f"flip_{duel.id}")]
                ])
            )
        except Exception as e:
            logger.error(f"❌ Error notifying room creator: {e}")

        logger.info(f"✅ User {user_id} joined room {room_code}, duel {duel.id} created")

    except Exception as e:
        logger.error(f"❌ Error joining room {room_code}: {e}")
        await callback.answer("❌ Ошибка присоединения к комнате", show_alert=True)

    await callback.answer()