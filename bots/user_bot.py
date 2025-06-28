"""
User bot на Telethon для отправки графиков цен в каналах
"""
import asyncio
import os
from datetime import datetime, timedelta
from typing import Dict, Set

from telethon import TelegramClient, events
from telethon.tl.types import Message

from config.settings import CHANNEL_IDS, MORI_TOKEN_MINT
from services.jupiter_service import jupiter_service, format_price_message
from services.chart_service import chart_service  # Новый сервис для графиков
from utils.logger import setup_logger

logger = setup_logger(__name__)

# Настройки для user bot
API_ID = int(os.getenv('TELEGRAM_API_ID', '0'))  # Получите на my.telegram.org
API_HASH = os.getenv('TELEGRAM_API_HASH', '')
PHONE = os.getenv('TELEGRAM_PHONE', '')  # Ваш номер телефона
SESSION_NAME = 'mori_user_bot'

# Антиспам настройки
class AntiSpam:
    def __init__(self):
        self.last_requests: Dict[int, datetime] = {}  # chat_id -> last_request_time
        self.user_requests: Dict[int, int] = {}  # user_id -> request_count_today
        self.daily_reset_time = datetime.now().replace(hour=0, minute=0, second=0)

        # Настройки лимитов
        self.CHAT_COOLDOWN = timedelta(minutes=5)  # Минимум 5 минут между запросами в чате
        self.USER_DAILY_LIMIT = 10  # Максимум 10 запросов от одного пользователя в день
        self.GLOBAL_DAILY_LIMIT = 100  # Максимум 100 запросов в день всего
        self.global_requests_today = 0

    def can_process_request(self, chat_id: int, user_id: int) -> tuple[bool, str]:
        """Проверить, можно ли обработать запрос"""
        now = datetime.now()

        # Сброс дневных счетчиков
        if now.date() > self.daily_reset_time.date():
            self.user_requests.clear()
            self.global_requests_today = 0
            self.daily_reset_time = now.replace(hour=0, minute=0, second=0)

        # Проверка глобального дневного лимита
        if self.global_requests_today >= self.GLOBAL_DAILY_LIMIT:
            return False, "🚫 Превышен дневной лимит запросов"

        # Проверка лимита пользователя
        user_requests = self.user_requests.get(user_id, 0)
        if user_requests >= self.USER_DAILY_LIMIT:
            return False, f"🚫 Вы превысили дневной лимит ({self.USER_DAILY_LIMIT} запросов)"

        # Проверка кулдауна чата
        last_request = self.last_requests.get(chat_id)
        if last_request and (now - last_request) < self.CHAT_COOLDOWN:
            remaining = self.CHAT_COOLDOWN - (now - last_request)
            minutes = int(remaining.total_seconds() // 60)
            return False, f"⏰ Следующий запрос через {minutes} мин"

        return True, ""

    def register_request(self, chat_id: int, user_id: int):
        """Зарегистрировать запрос"""
        now = datetime.now()
        self.last_requests[chat_id] = now
        self.user_requests[user_id] = self.user_requests.get(user_id, 0) + 1
        self.global_requests_today += 1

        logger.info(f"📊 Registered request: chat {chat_id}, user {user_id}, "
                   f"user_today: {self.user_requests[user_id]}, global_today: {self.global_requests_today}")


# Глобальный антиспам
anti_spam = AntiSpam()

# Создаем клиента
client = TelegramClient(SESSION_NAME, API_ID, API_HASH)


@client.on(events.NewMessage(pattern='/курс'))
async def price_command(event):
    """Обработчик команды /курс"""
    try:
        chat_id = event.chat_id
        user_id = event.sender_id

        # Проверяем разрешенные чаты
        if CHANNEL_IDS and chat_id not in CHANNEL_IDS:
            logger.warning(f"⚠️ Price command in unauthorized chat: {chat_id}")
            return

        # Проверяем антиспам
        can_process, error_msg = anti_spam.can_process_request(chat_id, user_id)
        if not can_process:
            # Отправляем личное сообщение с ошибкой, чтобы не спамить в чате
            try:
                await client.send_message(user_id, f"❌ {error_msg}")
            except:
                pass  # Если не можем отправить ЛС, просто игнорируем
            return

        # Регистрируем запрос
        anti_spam.register_request(chat_id, user_id)

        # Отправляем индикатор печати
        async with client.action(chat_id, 'typing'):
            # Получаем данные о цене
            logger.info(f"🔍 Fetching MORI price data for chat {chat_id}")
            price_data = await jupiter_service.get_mori_price()

            if not price_data:
                await event.reply("❌ Не удалось получить данные о цене MORI")
                return

            # Генерируем график
            logger.info(f"📊 Generating chart for MORI")
            chart_path = await chart_service.generate_candlestick_chart(
                token_mint=MORI_TOKEN_MINT,
                period="24h",
                style="dark_yellow"  # Черный фон с желтыми элементами
            )

            # Форматируем сообщение
            price_message = await format_advanced_price_message(price_data)

            if chart_path and os.path.exists(chart_path):
                # Отправляем график с текстом
                await client.send_file(
                    chat_id,
                    chart_path,
                    caption=price_message,
                    parse_mode='md'
                )

                # Удаляем временный файл
                try:
                    os.remove(chart_path)
                except:
                    pass

                logger.info(f"✅ Sent price chart to chat {chat_id}")
            else:
                # Если график не удалось создать, отправляем только текст
                await event.reply(price_message, parse_mode='md')
                logger.info(f"✅ Sent price text to chat {chat_id}")

    except Exception as e:
        logger.error(f"❌ Error in price command: {e}")
        try:
            await event.reply("❌ Ошибка получения данных о цене")
        except:
            pass


@client.on(events.NewMessage(pattern='/график'))
async def chart_command(event):
    """Обработчик команды /график - только график без текста"""
    try:
        chat_id = event.chat_id
        user_id = event.sender_id

        if CHANNEL_IDS and chat_id not in CHANNEL_IDS:
            return

        can_process, error_msg = anti_spam.can_process_request(chat_id, user_id)
        if not can_process:
            try:
                await client.send_message(user_id, f"❌ {error_msg}")
            except:
                pass
            return

        anti_spam.register_request(chat_id, user_id)

        async with client.action(chat_id, 'upload_photo'):
            chart_path = await chart_service.generate_candlestick_chart(
                token_mint=MORI_TOKEN_MINT,
                period="24h",
                style="dark_yellow"
            )

            if chart_path and os.path.exists(chart_path):
                await client.send_file(
                    chat_id,
                    chart_path,
                    caption="📊 График MORI/SOL за 24 часа"
                )

                try:
                    os.remove(chart_path)
                except:
                    pass

                logger.info(f"✅ Sent chart to chat {chat_id}")
            else:
                await event.reply("❌ Не удалось создать график")

    except Exception as e:
        logger.error(f"❌ Error in chart command: {e}")


@client.on(events.NewMessage(pattern='/статус'))
async def status_command(event):
    """Команда статуса антиспама (только для админов)"""
    try:
        user_id = event.sender_id

        # Проверяем, что это админ (можно добавить список админов)
        # Пока просто логируем

        stats = f"""📊 Статус системы

🕒 Сегодня запросов: {anti_spam.global_requests_today}/{anti_spam.GLOBAL_DAILY_LIMIT}
👤 Ваших запросов: {anti_spam.user_requests.get(user_id, 0)}/{anti_spam.USER_DAILY_LIMIT}
⏰ Кулдаун чатов: {int(anti_spam.CHAT_COOLDOWN.total_seconds() // 60)} мин

🎯 Разрешенные чаты: {len(CHANNEL_IDS) if CHANNEL_IDS else 'Все'}"""

        await event.reply(stats)

    except Exception as e:
        logger.error(f"❌ Error in status command: {e}")


async def format_advanced_price_message(price_data: dict) -> str:
    """Форматировать расширенное сообщение с ценой"""
    try:
        price_usd = price_data["price_usd"]
        price_sol = price_data.get("price_sol")
        market_cap = price_data.get("market_cap") or price_data.get("calculated_market_cap")
        volume_24h = price_data.get("volume_24h")

        # Красивое форматирование с эмодзи
        message = f"""🪙 **MORI/SOL**

💰 **Цена:** ${price_usd:.6f}"""

        if price_sol:
            message += f" ({price_sol:.6f} SOL)"

        if market_cap:
            if market_cap >= 1_000_000:
                message += f"\n📊 **MCAP:** ${market_cap / 1_000_000:.1f}M"
            else:
                message += f"\n📊 **MCAP:** ${market_cap:,.0f}"

        if volume_24h:
            if volume_24h >= 1_000_000:
                message += f"\n📈 **Volume 24h:** ${volume_24h / 1_000_000:.1f}M"
            else:
                message += f"\n📈 **Volume 24h:** ${volume_24h:,.0f}"

        # Добавляем ссылки для торговли
        message += f"""

🔗 **Торговля:**
• [Raydium](https://raydium.io/swap/?inputCurrency=sol&outputCurrency={MORI_TOKEN_MINT})
• [Jupiter](https://jup.ag/swap/SOL-{MORI_TOKEN_MINT})

⏰ {datetime.now().strftime('%H:%M UTC')}"""

        return message

    except Exception as e:
        logger.error(f"❌ Error formatting price message: {e}")
        return "❌ Ошибка форматирования данных"


async def setup_user_bot():
    """Настройка user bot"""
    try:
        logger.info("🔧 Setting up user bot...")

        # Проверяем настройки
        if not API_ID or not API_HASH:
            logger.error("❌ API_ID and API_HASH must be set in environment")
            return False

        # Подключаемся
        await client.start(phone=PHONE)

        # Получаем информацию о себе
        me = await client.get_me()
        logger.info(f"✅ User bot started as: {me.first_name} (@{me.username})")
        logger.info(f"📋 Authorized channels: {CHANNEL_IDS}")
        logger.info(f"🛡️ Anti-spam: {anti_spam.CHAT_COOLDOWN.total_seconds()//60}min cooldown, "
                   f"{anti_spam.USER_DAILY_LIMIT} per user/day")

        return True

    except Exception as e:
        logger.error(f"❌ Error setting up user bot: {e}")
        return False


async def user_bot_polling():
    """Запуск user bot"""
    try:
        if not await setup_user_bot():
            logger.error("❌ Failed to setup user bot")
            return

        logger.info("🚀 Starting user bot polling...")

        # Запускаем бота
        await client.run_until_disconnected()

    except KeyboardInterrupt:
        logger.info("🛑 User bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Error in user bot: {e}")
        raise
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(user_bot_polling())