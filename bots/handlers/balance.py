"""
Обработчики для управления балансом
"""
from decimal import Decimal

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.models.user import User
from database.models.transaction import Transaction, TransactionType, TransactionStatus
from services.solana_service import solana_service
from bots.keyboards.main_menu import get_main_menu
from config.settings import BOT_WALLET_ADDRESS, WITHDRAWAL_COMMISSION
from utils.logger import setup_logger

router = Router()
logger = setup_logger(__name__)


class BalanceStates(StatesGroup):
    waiting_for_withdrawal_amount = State()


@router.callback_query(F.data == "balance")
async def show_balance(callback: CallbackQuery):
    """Показать баланс пользователя"""
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

    # Получаем последние транзакции
    transactions = await Transaction.get_user_transactions(user.id, limit=5)

    balance_text = f"""📊 Ваш баланс

💰 Доступно: {user.balance:,.2f} MORI
👛 Кошелек: `{user.wallet_address[:8]}...{user.wallet_address[-4:]}`

📈 Статистика:
🎮 Игр сыграно: {user.total_games}
🏆 Побед: {user.wins} ({user.get_win_rate():.1f}%)
💎 Общая прибыль: {user.get_profit():+,.2f} MORI"""

    if transactions:
        balance_text += "\n\n📝 Последние операции:"
        for tx in transactions[:3]:
            status_emoji = "✅" if tx.status == TransactionStatus.COMPLETED else "⏳"
            balance_text += f"\n{status_emoji} {tx.get_display_type()}: {tx.amount:+,.2f} MORI"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💰 Пополнить", callback_data="deposit"),
            InlineKeyboardButton(text="💸 Вывести", callback_data="withdraw")
        ],
        [
            InlineKeyboardButton(text="📋 История транзакций", callback_data="transaction_history")
        ],
        [
            InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")
        ]
    ])

    await callback.message.edit_text(
        balance_text,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data == "deposit")
async def deposit_menu(callback: CallbackQuery):
    """Меню пополнения"""
    user_id = callback.from_user.id
    user = await User.get_by_telegram_id(user_id)

    if not user:
        await callback.answer("❌ Пользователь не найден!", show_alert=True)
        return

    deposit_text = f"""💰 Пополнение баланса

Отправьте MORI токены на адрес:
`{BOT_WALLET_ADDRESS}`

📝 Инструкция:
1. Откройте ваш Solana кошелек
2. Отправьте MORI токены на указанный адрес
3. Баланс обновится автоматически через 1-2 минуты

⚡ Минимальная сумма: 1 MORI
💳 Комиссия сети: ~0.00025 SOL"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📋 Копировать адрес", callback_data="copy_deposit_address")
        ],
        [
            InlineKeyboardButton(text="🔄 Проверить баланс", callback_data="balance"),
            InlineKeyboardButton(text="❓ Помощь", callback_data="deposit_help")
        ],
        [
            InlineKeyboardButton(text="🔙 Назад", callback_data="balance")
        ]
    ])

    await callback.message.edit_text(
        deposit_text,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data == "copy_deposit_address")
async def copy_deposit_address(callback: CallbackQuery):
    """Копировать адрес для депозита"""
    await callback.answer(
        f"📋 Адрес скопирован: {BOT_WALLET_ADDRESS}",
        show_alert=True
    )


@router.callback_query(F.data == "deposit_help")
async def deposit_help(callback: CallbackQuery):
    """Помощь по пополнению"""
    help_text = """❓ Помощь по пополнению

🔍 Как найти MORI токен:
• Адрес контракта: `{}`
• Поиск по названию: "MORI"

💰 Популярные кошельки:
• Phantom Wallet
• Solflare
• Trust Wallet

⏰ Время зачисления:
• Обычно: 1-2 минуты
• Максимум: 10 минут

❌ Проблемы с пополнением?
Свяжитесь с поддержкой: @support""".format(solana_service.mori_mint or "токен_не_настроен")

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="deposit")]
    ])

    await callback.message.edit_text(
        help_text,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data == "withdraw")
async def withdraw_menu(callback: CallbackQuery):
    """Меню вывода средств"""
    user_id = callback.from_user.id
    user = await User.get_by_telegram_id(user_id)

    if not user:
        await callback.answer("❌ Пользователь не найден!", show_alert=True)
        return

    if user.balance <= 0:
        await callback.message.edit_text(
            """💸 Вывод средств

❌ У вас недостаточно средств для вывода!

💰 Текущий баланс: 0 MORI
💳 Минимум для вывода: 10 MORI""",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💰 Пополнить", callback_data="deposit")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data="balance")]
            ])
        )
        await callback.answer()
        return

    commission_amount = user.balance * Decimal(WITHDRAWAL_COMMISSION)
    net_amount = user.balance - commission_amount

    withdraw_text = f"""💸 Вывод средств

📊 Доступно: {user.balance:,.2f} MORI
💳 Комиссия ({WITHDRAWAL_COMMISSION * 100:.0f}%): {commission_amount:,.2f} MORI
📤 К выводу: {net_amount:,.2f} MORI

👛 На кошелек: `{user.wallet_address[:8]}...{user.wallet_address[-4:]}`

Введите сумму для вывода (до {user.balance:,.0f} MORI):"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💯 Вывести всё", callback_data=f"withdraw_all_{user.balance}"),
        ],
        [
            InlineKeyboardButton(text="🔄 Сменить кошелек", callback_data="wallet"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="balance")
        ]
    ])

    await callback.message.edit_text(
        withdraw_text,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

    # Устанавливаем состояние ожидания суммы
    from bots.main_bot import dp
    state = dp.fsm.get_context(bot=callback.bot, chat_id=callback.message.chat.id, user_id=user_id)
    await state.set_state(BalanceStates.waiting_for_withdrawal_amount)
    await callback.answer()


@router.callback_query(F.data.startswith("withdraw_all_"))
async def withdraw_all(callback: CallbackQuery):
    """Вывести все средства"""
    user_id = callback.from_user.id
    amount_str = callback.data.split("_")[2]

    try:
        amount = Decimal(amount_str)
        await process_withdrawal(callback, user_id, amount)
    except Exception as e:
        logger.error(f"❌ Error in withdraw_all: {e}")
        await callback.answer("❌ Ошибка обработки", show_alert=True)


@router.message(BalanceStates.waiting_for_withdrawal_amount)
async def process_withdrawal_amount(message: Message, state: FSMContext):
    """Обработка суммы вывода"""
    try:
        amount = Decimal(message.text.strip())

        if amount <= 0:
            await message.answer(
                "❌ Сумма должна быть больше нуля!",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="withdraw")]
                ])
            )
            return

        user = await User.get_by_telegram_id(message.from_user.id)
        if not user or user.balance < amount:
            await message.answer(
                "❌ Недостаточно средств!",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="balance")]
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
        await process_withdrawal(fake_callback, message.from_user.id, amount)

    except ValueError:
        await message.answer(
            "❌ Введите корректное число!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="withdraw")]
            ])
        )
    except Exception as e:
        logger.error(f"❌ Error processing withdrawal amount: {e}")
        await message.answer("❌ Ошибка обработки суммы")

    await state.clear()


async def process_withdrawal(callback, user_id: int, amount: Decimal):
    """Обработать вывод средств"""
    try:
        user = await User.get_by_telegram_id(user_id)
        if not user:
            await callback.message.edit_text("❌ Пользователь не найден!")
            return

        if user.balance < amount:
            await callback.message.edit_text(
                f"❌ Недостаточно средств!\n\nДоступно: {user.balance:,.2f} MORI",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="balance")]
                ])
            )
            return

        # Рассчитываем комиссию
        commission = amount * Decimal(WITHDRAWAL_COMMISSION)
        net_amount = amount - commission

        # Показываем подтверждение
        confirm_text = f"""💸 Подтверждение вывода

💰 Сумма: {amount:,.2f} MORI
💳 Комиссия: {commission:,.2f} MORI
📤 К выводу: {net_amount:,.2f} MORI

👛 На адрес: `{user.wallet_address}`

Подтвердите операцию:"""

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_withdraw_{amount}"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="balance")
            ]
        ])

        await callback.message.edit_text(
            confirm_text,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"❌ Error in process_withdrawal: {e}")
        await callback.message.edit_text("❌ Ошибка обработки вывода")


@router.callback_query(F.data.startswith("confirm_withdraw_"))
async def confirm_withdrawal(callback: CallbackQuery):
    """Подтвердить вывод"""
    user_id = callback.from_user.id
    amount_str = callback.data.split("_")[2]

    try:
        amount = Decimal(amount_str)
        user = await User.get_by_telegram_id(user_id)

        if not user or user.balance < amount:
            await callback.message.edit_text(
                "❌ Недостаточно средств!",
                reply_markup=get_main_menu()
            )
            await callback.answer()
            return

        # Снимаем средства с баланса
        if not await user.subtract_balance(amount):
            await callback.message.edit_text(
                "❌ Ошибка списания средств!",
                reply_markup=get_main_menu()
            )
            await callback.answer()
            return

        # Рассчитываем выплату
        commission = amount * Decimal(WITHDRAWAL_COMMISSION)
        net_amount = amount - commission

        # Создаем транзакцию
        transaction = await Transaction.create_transaction(
            user.id,
            TransactionType.WITHDRAWAL,
            net_amount,
            to_address=user.wallet_address,
            description=f"Вывод {amount} MORI (комиссия {commission})"
        )

        # Показываем процесс
        await callback.message.edit_text(
            f"""⏳ Обработка вывода...

💰 Сумма: {net_amount:,.2f} MORI
👛 На кошелек: {user.wallet_address[:8]}...{user.wallet_address[-4:]}

🔄 Отправка транзакции..."""
        )

        # Отправляем токены
        tx_hash = await solana_service.send_token(
            user.wallet_address,
            net_amount,
            solana_service.mori_mint
        )

        if tx_hash and len(tx_hash) > 10:  # Проверяем что получили реальный хеш
            # Успешно отправлено
            await transaction.complete_transaction(tx_hash)

            success_text = f"""✅ Вывод выполнен!

        💰 Отправлено: {net_amount:,.2f} MORI
        💳 Комиссия: {commission:,.2f} MORI
        🔗 TX: `{tx_hash[:16]}...`
        👛 На кошелек: {user.wallet_address[:8]}...{user.wallet_address[-4:]}

        💰 Новый баланс: {user.balance:,.2f} MORI

        ⏰ Транзакция обрабатывается сетью Solana
        Токены поступят в течение 1-2 минут"""

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📊 Баланс", callback_data="balance")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ])

        else:
            # Ошибка отправки - возвращаем деньги
            await user.add_balance(amount)
            await transaction.fail_transaction("Ошибка отправки в сеть Solana")

            success_text = f"""❌ Ошибка вывода!

        Средства возвращены на баланс.
        💰 Баланс: {user.balance:,.2f} MORI

        🔧 Возможные причины:
        • Недостаточно SOL на кошельке бота для газа
        • Проблемы с сетью Solana
        • Неверный адрес получателя

        Попробуйте позже или обратитесь в поддержку."""

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="withdraw")],
                [InlineKeyboardButton(text="👛 Проверить кошелек", callback_data="wallet")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ])

        await callback.message.edit_text(
            success_text,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"❌ Error confirming withdrawal: {e}")
        await callback.message.edit_text(
            "❌ Ошибка при выводе средств",
            reply_markup=get_main_menu()
        )

    await callback.answer()


@router.callback_query(F.data == "transaction_history")
async def show_transaction_history(callback: CallbackQuery):
    """Показать историю транзакций"""
    user_id = callback.from_user.id
    user = await User.get_by_telegram_id(user_id)

    if not user:
        await callback.answer("❌ Пользователь не найден!", show_alert=True)
        return

    transactions = await Transaction.get_user_transactions(user.id, limit=10)

    if not transactions:
        history_text = """📋 История транзакций

Пока нет транзакций."""
    else:
        history_text = "📋 История транзакций\n\n"

        for tx in transactions:
            date_str = tx.created_at.strftime('%d.%m %H:%M')
            status_emoji = {
                "completed": "✅",
                "pending": "⏳",
                "failed": "❌",
                "cancelled": "🚫"
            }.get(tx.status.value, "❓")

            history_text += f"{status_emoji} {tx.get_display_type()}\n"
            history_text += f"💰 {tx.amount:+,.2f} MORI\n"
            history_text += f"📅 {date_str}\n"
            if tx.tx_hash:
                history_text += f"🔗 {tx.tx_hash[:12]}...\n"
            history_text += "\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="balance")]
    ])

    await callback.message.edit_text(
        history_text,
        reply_markup=keyboard
    )
    await callback.answer()