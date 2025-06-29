"""
Middleware для обработки ошибок Telegram
"""
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest, TelegramRetryAfter
import asyncio
from utils.logger import setup_logger

logger = setup_logger(__name__)


class ErrorHandlerMiddleware(BaseMiddleware):
    """Middleware для обработки ошибок Telegram"""

    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any]
    ) -> Any:
        try:
            return await handler(event, data)

        except TelegramForbiddenError as e:
            # Пользователь заблокировал бота
            if isinstance(event, Update) and event.message:
                user_id = event.message.from_user.id
                logger.warning(f"🚫 User {user_id} blocked the bot")
            elif isinstance(event, Update) and event.callback_query:
                user_id = event.callback_query.from_user.id
                logger.warning(f"🚫 User {user_id} blocked the bot")
            else:
                logger.warning(f"🚫 Bot was blocked by unknown user: {e}")

            # Не прерываем работу бота, просто логируем
            return None

        except TelegramBadRequest as e:
            # Плохой запрос (например, сообщение уже удалено)
            logger.warning(f"⚠️ Bad request: {e}")
            return None

        except TelegramRetryAfter as e:
            # Rate limit - ждем и повторяем
            logger.warning(f"⏳ Rate limit: waiting {e.retry_after} seconds")
            await asyncio.sleep(e.retry_after)
            return await handler(event, data)

        except Exception as e:
            # Другие ошибки
            logger.error(f"❌ Unexpected error in middleware: {e}")
            return None


class UserBlockedMiddleware(BaseMiddleware):
    """Специальный middleware для отслеживания заблокированных пользователей"""

    def __init__(self):
        self.blocked_users = set()  # Кеш заблокированных пользователей

    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any]
    ) -> Any:

        # Получаем user_id
        user_id = None
        if isinstance(event, Update):
            if event.message:
                user_id = event.message.from_user.id
            elif event.callback_query:
                user_id = event.callback_query.from_user.id

        # Если пользователь в списке заблокированных, пропускаем
        if user_id and user_id in self.blocked_users:
            logger.debug(f"🚫 Skipping update for blocked user {user_id}")
            return None

        try:
            return await handler(event, data)
        except TelegramForbiddenError:
            # Добавляем пользователя в список заблокированных
            if user_id:
                self.blocked_users.add(user_id)
                logger.info(f"🚫 Added user {user_id} to blocked list")
            raise  # Пропускаем дальше для обработки в ErrorHandlerMiddleware