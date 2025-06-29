"""
Обработчики для управления кошельком
"""
import asyncio
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.models.user import User
from database.models.wallet_history import WalletHistory
from services.solana_service import validate_solana_address
from bots.keyboards.main_menu import get_main_menu
from utils.logger import setup_logger

router = Router()
logger = setup_logger(__name__)


class WalletStates(StatesGroup):
    """Состояния FSM для работы с кошельками"""
    waiting_for_address = State()  # Ожидание первого кошелька при регистрации
    waiting_for_new_address = State()  # Ожидание нового кошелька при смене


@router.callback_query(F.data == "wallet")
async def wallet_menu(callback: CallbackQuery):
    """Показать меню управления кошельком"""
    user_id = callback.from_user.id

    try:
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

        # Форматируем дату последнего обновления
        updated_date = user.wallet_updated_at.strftime('%d.%m.%Y %H:%M')

        # Создаем клавиатуру
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 Сменить кошелек", callback_data="change_wallet"),
                InlineKeyboardButton(text="📋 Копировать адрес", callback_data="copy_wallet")
            ],
            [
                InlineKeyboardButton(text="📝 История изменений", callback_data="wallet_history")
            ],
            [
                InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")
            ]
        ])

        # Отправляем информацию о кошельке
        await callback.message.edit_text(
            f"""👛 Управление кошельком

💳 Текущий адрес:
`{user.wallet_address}`

📅 Последнее обновление: {updated_date}

ℹ️ На этот адрес отправляются:
• Выигрыши в дуэлях  
• Выводы средств
• Возвраты при отмене игр""",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"❌ Error in wallet_menu: {e}")
        await callback.answer("❌ Ошибка загрузки кошелька", show_alert=True)


@router.callback_query(F.data == "copy_wallet")
async def copy_wallet_address(callback: CallbackQuery):
    """Копировать адрес кошелька"""
    user_id = callback.from_user.id

    try:
        user = await User.get_by_telegram_id(user_id)

        if user:
            # Показываем адрес для копирования
            await callback.answer(
                f"📋 Адрес скопирован:\n{user.wallet_address}",
                show_alert=True
            )
            logger.info(f"✅ User {user_id} copied wallet address")
        else:
            await callback.answer("❌ Ошибка: пользователь не найден", show_alert=True)

    except Exception as e:
        logger.error(f"❌ Error copying wallet address: {e}")
        await callback.answer("❌ Ошибка копирования адреса", show_alert=True)


@router.callback_query(F.data == "change_wallet")
async def change_wallet_start(callback: CallbackQuery, state: FSMContext):
    """Начать процесс смены кошелька"""
    try:
        # Предупреждение о смене кошелька
        warning_text = """🔄 Смена кошелька

⚠️ Внимание! 
После смены адреса:
• Все будущие выплаты пойдут на новый адрес
• Выводы средств будут на новый адрес
• Старый адрес больше не будет использоваться

📝 Убедитесь, что у вас есть доступ к новому кошельку

👛 Отправьте новый адрес Solana кошелька:"""

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="wallet")]
        ])

        await callback.message.edit_text(warning_text, reply_markup=keyboard)

        # Устанавливаем состояние ожидания нового адреса
        await state.set_state(WalletStates.waiting_for_new_address)
        await callback.answer()

        logger.info(f"✅ User {callback.from_user.id} started wallet change process")

    except Exception as e:
        logger.error(f"❌ Error starting wallet change: {e}")
        await callback.answer("❌ Ошибка начала смены кошелька", show_alert=True)


@router.message(WalletStates.waiting_for_new_address)
async def process_new_wallet_address(message: Message, state: FSMContext):
    """Обработка нового адреса кошелька при смене"""
    new_address = message.text.strip()
    user_id = message.from_user.id

    try:
        # Базовая валидация адреса Solana
        if not validate_solana_address(new_address):
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="wallet")]
            ])

            await message.answer(
                """❌ Неверный адрес кошелька!

📝 Адрес Solana должен быть длиной 32-44 символа
Пример корректного адреса:
`9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM`

👛 Попробуйте еще раз или отмените операцию:""",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            return

        # Показываем процесс проверки
        checking_msg = await message.answer("🔍 Проверяем кошелек в сети Solana...")

        # Расширенная валидация - проверяем существование в сети
        from services.solana_service import solana_service

        try:
            # Проверяем, существует ли кошелек в сети
            sol_balance = await solana_service.get_sol_balance(new_address)

            if sol_balance is None:
                await checking_msg.edit_text(
                    """⚠️ Внимание! Кошелек не найден в сети Solana

Возможные причины:
• Кошелек еще не активирован (не получал SOL)
• Ошибка в адресе

Вы все еще хотите привязать этот адрес?""",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [
                            InlineKeyboardButton(text="✅ Да, привязать", callback_data=f"confirm_wallet_{new_address}"),
                            InlineKeyboardButton(text="❌ Отмена", callback_data="wallet")
                        ]
                    ])
                )
                await state.clear()
                return

            elif sol_balance == 0:
                await checking_msg.edit_text(
                    f"""⚠️ Кошелек найден, но баланс SOL: 0

Для получения токенов нужно иметь небольшое количество SOL для газа (~0.001 SOL)

Рекомендуем пополнить кошелек SOL перед использованием.

Привязать этот кошелек?""",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [
                            InlineKeyboardButton(text="✅ Да, привязать", callback_data=f"confirm_wallet_{new_address}"),
                            InlineKeyboardButton(text="❌ Отмена", callback_data="wallet")
                        ]
                    ])
                )
                await state.clear()
                return

            else:
                # Кошелек существует и имеет SOL - все хорошо
                await checking_msg.edit_text(
                    f"""✅ Кошелек проверен!

💰 SOL баланс: {sol_balance:.4f} SOL
🟢 Статус: Активен

Привязать этот кошелек?""",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [
                            InlineKeyboardButton(text="✅ Да, привязать", callback_data=f"confirm_wallet_{new_address}"),
                            InlineKeyboardButton(text="❌ Отмена", callback_data="wallet")
                        ]
                    ])
                )
                await state.clear()
                return

        except Exception as e:
            logger.error(f"❌ Error checking wallet in network: {e}")
            await checking_msg.edit_text(
                """⚠️ Не удалось проверить кошелек в сети

Возможно, проблемы с RPC-узлом Solana.
Адрес валиден, но сетевая проверка недоступна.

Привязать этот кошелек?""",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="✅ Да, привязать", callback_data=f"confirm_wallet_{new_address}"),
                        InlineKeyboardButton(text="❌ Отмена", callback_data="wallet")
                    ]
                ])
            )
            await state.clear()
            return

    except Exception as e:
        logger.error(f"❌ Error processing new wallet address: {e}")
        await message.answer(
            "❌ Произошла ошибка при обработке адреса. Попробуйте позже.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад в кошелек", callback_data="wallet")]
            ])
        )
        await state.clear()


@router.callback_query(F.data.startswith("confirm_wallet_"))
async def confirm_wallet_change(callback: CallbackQuery):
    """Подтвердить смену кошелька"""
    try:
        # Извлекаем адрес из callback_data
        new_address = callback.data.replace("confirm_wallet_", "")
        user_id = callback.from_user.id

        # Получаем пользователя
        user = await User.get_by_telegram_id(user_id)
        if not user:
            await callback.message.edit_text("❌ Пользователь не найден!")
            await callback.answer()
            return

        # Проверяем, не тот же ли это адрес
        if user.wallet_address.lower() == new_address.lower():
            await callback.message.edit_text(
                "⚠️ Это тот же адрес, что уже привязан к вашему аккаунту!",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад в кошелек", callback_data="wallet")]
                ])
            )
            await callback.answer()
            return

        # Сохраняем старый адрес для отображения
        old_address = user.wallet_address

        # Обновляем кошелек в базе данных
        success = await user.update_wallet(new_address)

        if success:
            # Создаем клавиатуру для успешного обновления
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="👛 Управление кошельком", callback_data="wallet")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ])

            await callback.message.edit_text(
                f"""✅ Кошелек успешно обновлен!

📤 Старый адрес:
`{old_address[:16]}...{old_address[-8:]}`

📥 Новый адрес:
`{new_address[:16]}...{new_address[-8:]}`

💡 Все будущие выплаты будут отправляться на новый адрес""",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )

            logger.info(f"✅ User {user_id} updated wallet from {old_address[:8]}... to {new_address[:8]}...")

        else:
            await callback.message.edit_text(
                "❌ Ошибка обновления кошелька в базе данных. Попробуйте позже.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад в кошелек", callback_data="wallet")]
                ])
            )
            logger.error(f"❌ Failed to update wallet for user {user_id}")

        await callback.answer()

    except Exception as e:
        logger.error(f"❌ Error confirming wallet change: {e}")
        await callback.message.edit_text(
            "❌ Произошла ошибка при подтверждении. Попробуйте позже.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад в кошелек", callback_data="wallet")]
            ])
        )
        await callback.answer()


@router.callback_query(F.data == "wallet_history")
async def show_wallet_history(callback: CallbackQuery):
    """Показать историю смены кошельков"""
    user_id = callback.from_user.id

    try:
        user = await User.get_by_telegram_id(user_id)

        if not user:
            await callback.answer("❌ Пользователь не найден!", show_alert=True)
            return

        # Получаем историю изменений кошельков
        history = await WalletHistory.get_user_history(user.id, limit=10)

        if not history:
            text = """📝 История изменений кошелька

📭 Пока нет записей об изменениях кошелька.
Это ваш первый и единственный кошелек."""
        else:
            text = "📝 История изменений кошелька\n\n"

            for i, record in enumerate(history, 1):
                date_str = record.changed_at.strftime('%d.%m.%Y %H:%M')

                if record.old_address:
                    # Смена кошелька
                    text += f"🔄 Изменение #{i}\n"
                    text += f"📅 {date_str}\n"
                    text += f"📤 Старый: {record.old_address[:12]}...{record.old_address[-6:]}\n"
                    text += f"📥 Новый: {record.new_address[:12]}...{record.new_address[-6:]}\n\n"
                else:
                    # Первая привязка
                    text += f"🆕 Первая привязка\n"
                    text += f"📅 {date_str}\n"
                    text += f"👛 Адрес: {record.new_address[:12]}...{record.new_address[-6:]}\n\n"

        # Создаем клавиатуру
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад в кошелек", callback_data="wallet")]
        ])

        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()

        logger.info(f"✅ Showed wallet history for user {user_id}")

    except Exception as e:
        logger.error(f"❌ Error showing wallet history: {e}")
        await callback.answer("❌ Ошибка загрузки истории", show_alert=True)


@router.message(WalletStates.waiting_for_address)
async def process_first_wallet_address(message: Message, state: FSMContext):
    """Обработка первого адреса кошелька при регистрации нового пользователя"""
    wallet_address = message.text.strip()
    user_id = message.from_user.id
    username = message.from_user.username

    try:
        # Валидация адреса Solana
        if not validate_solana_address(wallet_address):
            await message.answer(
                """❌ Неверный адрес кошелька!

📝 Адрес Solana должен быть длиной 32-44 символа
Пример корректного адреса:
`9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM`

👛 Попробуйте еще раз:""",
                parse_mode="Markdown"
            )
            return

        # Проверяем, не зарегистрирован ли уже пользователь
        existing_user = await User.get_by_telegram_id(user_id)
        if existing_user:
            await message.answer(
                "✅ Вы уже зарегистрированы в системе!",
                reply_markup=get_main_menu()
            )
            await state.clear()
            return

        # Создаем нового пользователя
        user = await User.create_user(
            telegram_id=user_id,
            wallet_address=wallet_address,
            username=username
        )

        if not user:
            await message.answer(
                "❌ Ошибка создания аккаунта. Попробуйте позже или обратитесь в поддержку."
            )
            await state.clear()
            return

        # Проверяем, есть ли отложенное присоединение к комнате
        data = await state.get_data()
        pending_room = data.get('pending_room')

        if pending_room and pending_room.startswith('room_'):
            room_code = pending_room.replace('room_', '')

            await message.answer(
                f"""✅ Кошелек успешно привязан!
💳 {wallet_address[:16]}...{wallet_address[-8:]}

🏠 Присоединяемся к комнате {room_code}..."""
            )

            # Обрабатываем присоединение к комнате
            await handle_room_join_after_registration(message, user, room_code)

        else:
            # Обычная регистрация без комнаты
            await message.answer(
                f"""✅ Добро пожаловать в MORI Duels!

👛 Кошелек привязан:
`{wallet_address[:16]}...{wallet_address[-8:]}`

💡 Теперь вы можете:
• Пополнить баланс MORI токенами
• Участвовать в дуэлях
• Создавать игровые комнаты

Начнем играть?""",
                reply_markup=get_main_menu(),
                parse_mode="Markdown"
            )

        logger.info(f"✅ New user registered: {user_id} with wallet {wallet_address[:8]}...")

        # Очищаем состояние FSM
        await state.clear()

    except Exception as e:
        logger.error(f"❌ Error creating user {user_id}: {e}")
        await message.answer(
            "❌ Произошла ошибка при создании аккаунта. Попробуйте позже."
        )
        await state.clear()


async def handle_room_join_after_registration(message: Message, user: User, room_code: str):
    """Обработать присоединение к комнате после регистрации"""
    try:
        from database.models.room import Room, RoomStatus

        # Получаем информацию о комнате
        room = await Room.get_by_code(room_code)

        if not room:
            await message.answer(
                f"""❌ Комната {room_code} не найдена!

Возможно, ссылка устарела или комната была закрыта.
Но вы успешно зарегистрированы и можете начать играть!""",
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

Но вы успешно зарегистрированы! Можете:""",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🏠 Найти другие комнаты", callback_data="rooms")],
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

Но вы успешно зарегистрированы и можете найти другие игры:""",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🏠 Все комнаты", callback_data="rooms")],
                    [InlineKeyboardButton(text="🎮 Быстрая игра", callback_data="quick_game")],
                    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
                ])
            )
            return

        # Проверяем, не создатель ли это комнаты
        if room.creator_id == user.id:
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
            f"""🏠 Информация о комнате {room_code}

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

        logger.info(f"✅ Showed room {room_code} info to new user {user.id}")

    except Exception as e:
        logger.error(f"❌ Error handling room join after registration: {e}")
        await message.answer(
            f"""❌ Ошибка при обработке комнаты {room_code}

Но вы успешно зарегистрированы! Попробуйте найти другие игры:""",
            reply_markup=get_main_menu()
        )


# Дополнительные вспомогательные функции

async def get_user_wallet_summary(user: User) -> str:
    """Получить краткую сводку по кошельку пользователя"""
    try:
        # Получаем количество изменений кошелька
        history_count = len(await WalletHistory.get_user_history(user.id))

        summary = f"""👛 Кошелек: `{user.wallet_address[:12]}...{user.wallet_address[-6:]}`
📅 Обновлен: {user.wallet_updated_at.strftime('%d.%m.%Y')}"""

        if history_count > 1:
            summary += f"\n🔄 Изменений: {history_count - 1}"

        return summary

    except Exception as e:
        logger.error(f"❌ Error getting wallet summary: {e}")
        return f"👛 Кошелек: `{user.wallet_address[:12]}...{user.wallet_address[-6:]}`"


async def validate_wallet_not_in_use(wallet_address: str, exclude_user_id: int = None) -> bool:
    """Проверить, что кошелек не используется другим пользователем"""
    try:
        # В будущем можно добавить проверку на дублирование кошельков
        # Пока возвращаем True (разрешаем любые кошельки)
        return True

    except Exception as e:
        logger.error(f"❌ Error validating wallet uniqueness: {e}")
        return True