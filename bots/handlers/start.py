from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

from bots.keyboards.main_menu import get_main_menu
from database.models.user import User
from bots.handlers.wallet import WalletStates
from utils.logger import setup_logger

router = Router()
logger = setup_logger(__name__)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    username = message.from_user.username

    # Проверяем, есть ли аргументы (например, ссылка на комнату)
    args = message.text.split()[1:] if len(message.text.split()) > 1 else []

    # Проверяем, есть ли пользователь в БД
    user = await User.get_by_telegram_id(user_id)

    if not user:
        # Новый пользователь - нужно привязать кошелек
        welcome_text = """Добро пожаловать в MORI Duels! 🪙

Для игры нужно привязать Solana кошелек
На него будут отправляться выигрыши

👛 Отправьте адрес своего кошелька:"""

        # Если есть аргумент (например room_ABC123), сохраняем его
        if args and args[0].startswith('room_'):
            await state.update_data(pending_room=args[0])
            room_code = args[0].replace('room_', '')
            welcome_text += f"""

🏠 После регистрации вы присоединитесь к комнате: {room_code}"""

        await message.answer(welcome_text)
        await state.set_state(WalletStates.waiting_for_address)
        return

    # Существующий пользователь
    balance = await user.get_balance()

    # Проверяем, не хочет ли присоединиться к комнате
    if args and args[0].startswith('room_'):
        room_code = args[0].replace('room_', '')
        await handle_room_join_existing_user(message, user, room_code)
        return

    # Обычное приветствие для существующего пользователя
    await message.answer(
        f"""Добро пожаловать в MORI Duels! 🪙

💰 Баланс: {balance:,.2f} MORI
👛 Кошелек: {user.wallet_address[:8]}...{user.wallet_address[-4:]}

Выберите действие:""",
        reply_markup=get_main_menu()
    )


async def handle_room_join_existing_user(message: Message, user: User, room_code: str):
    """Обработать присоединение существующего пользователя к комнате"""
    try:
        from database.models.room import Room, RoomStatus
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

        # Получаем информацию о комнате
        room = await Room.get_by_code(room_code)

        if not room:
            await message.answer(
                f"""❌ Комната {room_code} не найдена!

Возможно, ссылка устарела или комната была закрыта.""",
                reply_markup=get_main_menu()
            )
            return

        # Проверяем статус комнаты
        if room.status != RoomStatus.WAITING:
            status_messages = {
                RoomStatus.FULL: "уже заполнена",
                RoomStatus.EXPIRED: "истекло время ожидания",
                RoomStatus.CLOSED: "была закрыта создателем"
            }
            status_text = status_messages.get(room.status, "недоступна")

            await message.answer(
                f"""❌ К сожалению, комната {room_code} {status_text}!

Но вы можете найти другие игры:""",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🏠 Все комнаты", callback_data="rooms")],
                    [InlineKeyboardButton(text="🎮 Быстрая игра", callback_data="quick_game")],
                    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
                ])
            )
            return

        # Проверяем, не истекла ли комната
        if room.is_expired():
            await room.expire_room()
            await message.answer(
                f"""❌ Время ожидания в комнате {room_code} истекло!

Попробуйте найти другие игры:""",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🏠 Все комнаты", callback_data="rooms")],
                    [InlineKeyboardButton(text="🎮 Быстрая игра", callback_data="quick_game")],
                    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
                ])
            )
            return

        # Проверяем, не создатель ли это комнаты
        if room.creator_id == user.telegram_id:
            await message.answer(
                f"""ℹ️ Это ваша собственная комната {room_code}!

💰 Ставка: {room.stake:,.0f} MORI
⏰ Ждем других игроков для присоединения...

Поделитесь ссылкой с друзьями или ждите случайных игроков!""",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="❌ Закрыть комнату", callback_data=f"close_room_{room_code}")],
                    [InlineKeyboardButton(text="🏠 Все комнаты", callback_data="rooms")]
                ])
            )
            return

        # Показываем информацию о комнате для присоединения
        creator = await User.get_by_telegram_id(room.creator_id)
        creator_name = creator.username if creator and creator.username else f"Player {room.creator_id}"
        time_left = room.get_time_left()
        minutes_left = max(0, int(time_left.total_seconds() // 60))

        await message.answer(
            f"""🏠 Приглашение в комнату {room_code}

👤 Создатель: @{creator_name}
💰 Ставка: {room.stake:,.0f} MORI
⏰ Осталось времени: {minutes_left} мин

Хотите присоединиться к игре?""",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎮 Присоединиться", callback_data=f"join_room_{room_code}")],
                [InlineKeyboardButton(text="🏠 Все комнаты", callback_data="rooms")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ])
        )

        logger.info(f"✅ Showed room {room_code} info to existing user {user.id}")

    except Exception as e:
        logger.error(f"❌ Error handling room join for existing user: {e}")
        await message.answer(
            f"""❌ Ошибка при обработке комнаты {room_code}

Попробуйте найти другие игры:""",
            reply_markup=get_main_menu()
        )


@router.callback_query(F.data == "main_menu")
async def back_to_main_menu(callback: CallbackQuery):
    """Возврат в главное меню"""
    user_id = callback.from_user.id
    user = await User.get_by_telegram_id(user_id)

    if not user:
        await callback.message.edit_text(
            """❌ Пользователь не найден!

Используйте /start для регистрации""",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Регистрация", callback_data="start")]
            ])
        )
        await callback.answer()
        return

    balance = await user.get_balance()
    await callback.message.edit_text(
        f"""Добро пожаловать в MORI Duels! 🪙

💰 Баланс: {balance:,.2f} MORI
👛 Кошелек: {user.wallet_address[:8]}...{user.wallet_address[-4:]}

Выберите действие:""",
        reply_markup=get_main_menu()
    )
    await callback.answer()