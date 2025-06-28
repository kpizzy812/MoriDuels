from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart

from bots.keyboards.main_menu import get_main_menu
from database.models.user import User
from utils.logger import setup_logger

router = Router()
logger = setup_logger(__name__)

@router.message(CommandStart())
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    username = message.from_user.username

    # Проверяем, есть ли пользователь в БД
    user = await User.get_by_telegram_id(user_id)

    if not user:
        # Новый пользователь - нужно привязать кошелек
        await message.answer(
            """Добро пожаловать в MORI Duels! 🪙

Для игры нужно привязать Solana кошелек
На него будут отправляться выигрыши

👛 Отправьте адрес своего кошелька:"""
        )
        return

    # Существующий пользователь
    balance = await user.get_balance()
    await message.answer(
        f"""Добро пожаловать в MORI Duels! 🪙

💰 Баланс: {balance:,.2f} MORI
👛 Кошелек: {user.wallet_address[:8]}...{user.wallet_address[-4:]}

Выберите действие:""",
        reply_markup=get_main_menu()
    )

@router.callback_query(F.data == "main_menu")
async def back_to_main_menu(callback: CallbackQuery):
    """Возврат в главное меню"""
    await callback.message.edit_text(
        """Добро пожаловать в MORI Duels! 🪙

Выберите действие:""",
        reply_markup=get_main_menu()
    )
    await callback.answer()
