"""
Пользовательский бот для команды /курс в каналах
"""
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
from aiogram.fsm.storage.memory import MemoryStorage

from config.settings import USER_BOT_TOKEN, CHANNEL_IDS, MORI_TOKEN_MINT
from services.jupiter_service import jupiter_service, format_price_message
from utils.logger import setup_logger

logger = setup_logger(__name__)

# Создаем бота и диспетчер
bot = Bot(token=USER_BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


@dp.message(Command("курс"))
async def price_command(message: Message):
    """Команда /курс для показа цены MORI"""

    # Проверяем, что команда вызвана в разрешенном чате
    chat_id = message.chat.id
    if CHANNEL_IDS and chat_id not in CHANNEL_IDS:
        logger.warning(f"⚠️ Price command called in unauthorized chat: {chat_id}")
        return

    try:
        # Отправляем индикатор загрузки
        loading_msg = await message.answer("🔄 Загружаем данные о цене MORI...")

        # Получаем данные о цене
        price_data = await jupiter_service.get_mori_price()

        if not price_data:
            await loading_msg.edit_text(
                "❌ Не удалось получить данные о цене MORI\n"
                "Попробуйте позже."
            )
            return

        # Форматируем сообщение
        price_message = format_price_message(price_data, "MORI")

        # Пытаемся отправить график (если есть)
        chart_path = await jupiter_service.generate_price_chart(MORI_TOKEN_MINT)

        if chart_path:
            try:
                chart_file = FSInputFile(chart_path)
                await loading_msg.delete()
                await message.answer_photo(
                    chart_file,
                    caption=price_message,
                    parse_mode="Markdown"
                )
                logger.info(f"✅ Sent price with chart to chat {chat_id}")
            except Exception as e:
                logger.error(f"❌ Error sending chart: {e}")
                # Если не удалось отправить график, отправляем просто текст
                await loading_msg.edit_text(price_message, parse_mode="Markdown")
        else:
            # Отправляем только текст
            await loading_msg.edit_text(price_message, parse_mode="Markdown")
            logger.info(f"✅ Sent price text to chat {chat_id}")

    except Exception as e:
        logger.error(f"❌ Error in price command: {e}")
        try:
            await loading_msg.edit_text(
                "❌ Ошибка получения данных о цене\n"
                "Попробуйте позже."
            )
        except:
            await message.answer("❌ Ошибка получения данных о цене")


@dp.message(Command("chart"))
async def chart_command(message: Message):
    """Команда /chart для показа графика"""

    # Проверяем разрешения
    chat_id = message.chat.id
    if CHANNEL_IDS and chat_id not in CHANNEL_IDS:
        return

    try:
        loading_msg = await message.answer("📊 Генерируем график MORI...")

        # Генерируем график
        chart_path = await jupiter_service.generate_price_chart(MORI_TOKEN_MINT, period="24h")

        if chart_path:
            try:
                chart_file = FSInputFile(chart_path)
                await loading_msg.delete()
                await message.answer_photo(
                    chart_file,
                    caption="📊 График цены MORI за 24 часа"
                )
                logger.info(f"✅ Sent chart to chat {chat_id}")
            except Exception as e:
                logger.error(f"❌ Error sending chart: {e}")
                await loading_msg.edit_text("❌ Ошибка отправки графика")
        else:
            await loading_msg.edit_text(
                "❌ График временно недоступен\n"
                "Используйте /курс для получения цены"
            )

    except Exception as e:
        logger.error(f"❌ Error in chart command: {e}")
        await message.answer("❌ Ошибка генерации графика")


@dp.message(Command("info"))
async def info_command(message: Message):
    """Команда /info для показа информации о токене"""

    # Проверяем разрешения
    chat_id = message.chat.id
    if CHANNEL_IDS and chat_id not in CHANNEL_IDS:
        return

    try:
        loading_msg = await message.answer("ℹ️ Загружаем информацию о MORI...")

        # Получаем расширенные данные
        market_data = await jupiter_service.get_market_data(MORI_TOKEN_MINT)

        if not market_data:
            await loading_msg.edit_text("❌ Не удалось получить информацию о токене")
            return

        # Форматируем подробную информацию
        info_message = f"""ℹ️ Информация о MORI

🏷️ Название: {market_data.get('name', 'MORI Token')}
🔖 Символ: {market_data.get('symbol', 'MORI')}
📍 Адрес: `{MORI_TOKEN_MINT}`

💰 Цена: ${market_data['price_usd']:.6f}"""

        if market_data.get('price_sol'):
            info_message += f" ({market_data['price_sol']:.6f} SOL)"

        if market_data.get('market_cap') or market_data.get('calculated_market_cap'):
            mcap = market_data.get('market_cap') or market_data.get('calculated_market_cap')
            if mcap >= 1_000_000:
                info_message += f"\n📊 Market Cap: ${mcap / 1_000_000:.1f}M"
            else:
                info_message += f"\n📊 Market Cap: ${mcap:,.0f}"

        if market_data.get('supply'):
            supply = market_data['supply']
            if supply >= 1_000_000_000:
                info_message += f"\n🪙 Supply: {supply / 1_000_000_000:.1f}B"
            elif supply >= 1_000_000:
                info_message += f"\n🪙 Supply: {supply / 1_000_000:.1f}M"
            else:
                info_message += f"\n🪙 Supply: {supply:,.0f}"

        if market_data.get('decimals'):
            info_message += f"\n🔢 Decimals: {market_data['decimals']}"

        info_message += f"\n\n🔗 Торговля:\n• [Raydium](https://raydium.io/swap/?inputCurrency=sol&outputCurrency={MORI_TOKEN_MINT})\n• [Jupiter](https://jup.ag/swap/SOL-{MORI_TOKEN_MINT})"

        await loading_msg.edit_text(info_message, parse_mode="Markdown")
        logger.info(f"✅ Sent token info to chat {chat_id}")

    except Exception as e:
        logger.error(f"❌ Error in info command: {e}")
        await message.answer("❌ Ошибка получения информации")


@dp.message(Command("help"))
async def help_command(message: Message):
    """Команда /help для показа доступных команд"""

    # Проверяем разрешения
    chat_id = message.chat.id
    if CHANNEL_IDS and chat_id not in CHANNEL_IDS:
        return

    help_text = """❓ Доступные команды:

/курс - Текущая цена MORI
/chart - График цены за 24ч
/info - Подробная информация о токене
/help - Эта справка

🎮 Хотите играть с MORI токенами?
Переходите к боту: @moriduels_bot"""

    await message.answer(help_text)
    logger.info(f"✅ Sent help to chat {chat_id}")


async def setup_user_bot():
    """Настройка пользовательского бота"""
    logger.info("🔧 Setting up user bot...")

    # Устанавливаем команды бота
    from aiogram.types import BotCommand
    await bot.set_my_commands([
        BotCommand(command="курс", description="💰 Цена MORI"),
        BotCommand(command="chart", description="📊 График цены"),
        BotCommand(command="info", description="ℹ️ Информация о токене"),
        BotCommand(command="help", description="❓ Помощь"),
    ])

    logger.info("✅ User bot setup complete")


async def user_bot_polling():
    """Запуск пользовательского бота"""
    try:
        await setup_user_bot()

        logger.info("🚀 Starting user bot polling...")
        logger.info(f"📋 Authorized channels: {CHANNEL_IDS}")

        await dp.start_polling(bot)

    except Exception as e:
        logger.error(f"❌ Error in user bot: {e}")
        raise
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(user_bot_polling())