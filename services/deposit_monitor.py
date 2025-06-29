"""
Сервис мониторинга депозитов
"""
import asyncio
from decimal import Decimal
from typing import Dict, Any, Set, Optional
from datetime import datetime

from database.models.user import User
from database.models.transaction import Transaction, TransactionType
from database.connection import async_session
from services.solana_service import solana_service
from config.settings import BOT_WALLET_ADDRESS, MORI_TOKEN_MINT
from utils.logger import setup_logger
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import text

logger = setup_logger(__name__)


class DepositMonitor:
    def __init__(self):
        self.monitoring = False
        self.last_processed_signature = None
        self.processed_signatures: Set[str] = set()  # Кеш обработанных транзакций
        self.check_interval = 30  # секунд

    async def start_monitoring(self):
        """Запустить мониторинг депозитов"""
        if self.monitoring:
            logger.warning("⚠️ Deposit monitoring already running")
            return

        self.monitoring = True
        logger.info("🔍 Starting deposit monitoring...")

        try:
            await self._monitor_loop()
        except Exception as e:
            logger.error(f"❌ Error in deposit monitoring: {e}")
        finally:
            self.monitoring = False

    async def stop_monitoring(self):
        """Остановить мониторинг"""
        self.monitoring = False
        logger.info("🛑 Deposit monitoring stopped")

    async def _monitor_loop(self):
        """Основной цикл мониторинга"""
        while self.monitoring:
            try:
                # Проверяем новые транзакции на адрес бота
                await self._check_new_transactions()

                # Ждем следующую проверку
                await asyncio.sleep(self.check_interval)

            except Exception as e:
                logger.error(f"❌ Error in monitoring loop: {e}")
                await asyncio.sleep(60)  # Увеличиваем интервал при ошибке

    async def _check_new_transactions(self):
        """Проверить новые транзакции"""
        try:
            if not BOT_WALLET_ADDRESS:
                logger.error("❌ Bot wallet address not configured")
                return

            # Получаем последние транзакции на адрес бота
            from solders.pubkey import Pubkey
            bot_pubkey = Pubkey.from_string(BOT_WALLET_ADDRESS)

            # Получаем подписи транзакций
            signatures_response = await solana_service.client.get_signatures_for_address(
                bot_pubkey,
                limit=20,
                before=self.last_processed_signature
            )

            if not signatures_response.value:
                return

            # Обрабатываем новые транзакции
            new_signatures = []
            for sig_info in signatures_response.value:
                signature = str(sig_info.signature)

                # Пропускаем уже обработанные
                if signature in self.processed_signatures:
                    continue

                # Пропускаем если это последняя обработанная
                if signature == self.last_processed_signature:
                    break

                new_signatures.append((signature, sig_info))

            # Обрабатываем в обратном порядке (от старых к новым)
            for signature, sig_info in reversed(new_signatures):
                await self._process_transaction(signature, sig_info)
                self.processed_signatures.add(signature)

            # Обновляем последнюю обработанную подпись
            if new_signatures:
                self.last_processed_signature = new_signatures[0][0]

            # Очищаем кеш если он стал слишком большим
            if len(self.processed_signatures) > 1000:
                # Оставляем только последние 500
                self.processed_signatures = set(list(self.processed_signatures)[-500:])

        except Exception as e:
            logger.error(f"❌ Error checking new transactions: {e}")

    async def _process_transaction(self, signature: str, sig_info):
        """Обработать транзакцию"""
        try:
            # Проверяем, что транзакция успешна
            if sig_info.err:
                logger.debug(f"⚠️ Skipping failed transaction {signature[:8]}...")
                return

            # Проверяем, обработана ли уже эта транзакция в БД
            if await self._is_transaction_processed(signature):
                logger.debug(f"⚠️ Transaction {signature[:8]}... already processed in DB")
                return

            # Парсим транзакцию на предмет MORI депозитов
            transfer_info = await solana_service.parse_token_transfer(signature)

            if transfer_info and transfer_info.get("type") == "deposit":
                # Проверяем, что это MORI токен
                if transfer_info["token_mint"] == MORI_TOKEN_MINT:
                    await self._process_deposit(transfer_info, signature, sig_info.block_time)

        except Exception as e:
            logger.error(f"❌ Error processing transaction {signature}: {e}")

    async def _process_deposit(self, deposit_info: Dict[str, Any], tx_hash: str, block_time: int):
        """Обработать депозит"""
        try:
            amount = deposit_info["amount"]
            account_address = deposit_info["account"]

            logger.info(f"💰 Processing deposit: {amount} MORI to account {account_address[:8]}...")

            # Находим пользователя по Associated Token Account
            user = await self._find_user_by_token_account(account_address)

            if not user:
                logger.warning(f"⚠️ No user found for token account {account_address}")
                return

            # Проверяем минимальную сумму депозита
            if amount < Decimal("1"):
                logger.warning(f"⚠️ Deposit amount too small: {amount} MORI")
                return

            # Создаем транзакцию депозита
            transaction = await Transaction.create_transaction(
                user.id,
                TransactionType.DEPOSIT,
                amount,
                tx_hash=tx_hash,
                from_address=account_address,  # Это ATA, не wallet пользователя
                to_address=BOT_WALLET_ADDRESS,
                description=f"Депозит {amount} MORI"
            )

            # Зачисляем средства на баланс
            if await user.add_balance(amount):
                await transaction.complete_transaction()

                # Уведомляем пользователя
                await self._notify_user_about_deposit(user, amount, tx_hash)

                logger.info(f"✅ Deposit processed: {amount} MORI for user {user.telegram_id}")
            else:
                await transaction.fail_transaction("Ошибка зачисления на баланс")
                logger.error(f"❌ Failed to add balance for user {user.telegram_id}")

        except Exception as e:
            logger.error(f"❌ Error processing deposit: {e}")

    async def _find_user_by_token_account(self, token_account: str) -> Optional[User]:
        """Найти пользователя по Associated Token Account"""
        try:
            # Получаем информацию о владельце токен аккаунта
            from solders.pubkey import Pubkey
            account_pubkey = Pubkey.from_string(token_account)

            account_info = await solana_service.client.get_account_info(account_pubkey)
            if not account_info.value or not account_info.value.data:
                return None

            # Парсим данные токен аккаунта чтобы получить owner
            data = account_info.value.data
            if len(data) < 32:
                return None

            # Owner находится в первых 32 байтах токен аккаунта
            owner_bytes = data[:32]
            owner_pubkey = Pubkey(owner_bytes)
            owner_address = str(owner_pubkey)

            # Ищем пользователя по wallet_address
            async with async_session() as session:
                result = await session.execute(
                    text("SELECT * FROM users WHERE wallet_address = :wallet_address"),
                    {"wallet_address": owner_address}
                )
                row = result.fetchone()
                if row:
                    user = User()
                    for key, value in row._mapping.items():
                        setattr(user, key, value)
                    return user

            return None

        except Exception as e:
            logger.error(f"❌ Error finding user by token account {token_account}: {e}")
            return None

    async def _is_transaction_processed(self, tx_hash: str) -> bool:
        """Проверить, обработана ли транзакция"""
        try:
            async with async_session() as session:
                result = await session.execute(
                    text("SELECT COUNT(*) FROM transactions WHERE tx_hash = :tx_hash"),
                    {"tx_hash": tx_hash}
                )
                count = result.scalar()
                return count > 0

        except Exception as e:
            logger.error(f"❌ Error checking transaction {tx_hash}: {e}")
            return False

    async def _notify_user_about_deposit(self, user: User, amount: Decimal, tx_hash: str):
        """Уведомить пользователя о депозите"""
        try:
            from bots.main_bot import bot

            message = f"""✅ Депозит зачислен!

💰 Сумма: {amount:,.2f} MORI
🔗 TX: {tx_hash[:12]}...
💳 Новый баланс: {user.balance:,.2f} MORI

Можете начинать играть! 🎮"""

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎮 Играть", callback_data="quick_game")],
                [InlineKeyboardButton(text="📊 Баланс", callback_data="balance")]
            ])

            await bot.send_message(
                user.telegram_id,
                message,
                reply_markup=keyboard
            )

            logger.info(f"📱 Notified user {user.telegram_id} about deposit")

        except Exception as e:
            logger.error(f"❌ Error notifying user about deposit: {e}")

    async def force_check_deposits(self, user_id: int = None) -> Dict[str, Any]:
        """Принудительная проверка депозитов (для админки)"""
        try:
            if user_id:
                # Проверяем депозиты конкретного пользователя
                user = await User.get_by_telegram_id(user_id)
                if not user:
                    return {"error": "Пользователь не найден"}

                # Получаем последние транзакции для его кошелька
                recent_txs = await solana_service.get_recent_token_transactions(
                    user.wallet_address,
                    limit=5
                )

                processed_count = 0
                for tx_info in recent_txs:
                    if not await self._is_transaction_processed(tx_info["signature"]):
                        await self._process_transaction(tx_info["signature"], type('obj', (object,), {
                            'err': None,
                            'block_time': tx_info.get("block_time")
                        })())
                        processed_count += 1

                return {
                    "success": True,
                    "user_id": user_id,
                    "processed": processed_count,
                    "checked": len(recent_txs)
                }
            else:
                # Общая принудительная проверка
                await self._check_new_transactions()
                return {"success": True, "message": "Force check completed"}

        except Exception as e:
            logger.error(f"❌ Error in force check deposits: {e}")
            return {"error": str(e)}

    async def get_monitoring_stats(self) -> Dict[str, Any]:
        """Получить статистику мониторинга"""
        try:
            async with async_session() as session:
                # Статистика депозитов за последние 24ч
                result = await session.execute(text("""
                    SELECT 
                        COUNT(*) as count_24h,
                        COALESCE(SUM(amount), 0) as sum_24h
                    FROM transactions 
                    WHERE type = 'deposit' 
                    AND status = 'completed'
                    AND created_at >= NOW() - INTERVAL '24 hours'
                """))
                stats_24h = result.fetchone()

                # Общая статистика депозитов
                result = await session.execute(text("""
                    SELECT 
                        COUNT(*) as total_count,
                        COALESCE(SUM(amount), 0) as total_sum,
                        COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_count
                    FROM transactions 
                    WHERE type = 'deposit'
                """))
                total_stats = result.fetchone()

                return {
                    "monitoring": self.monitoring,
                    "last_signature": self.last_processed_signature[:8] + "..." if self.last_processed_signature else None,
                    "processed_cache_size": len(self.processed_signatures),
                    "deposits_24h": {
                        "count": stats_24h.count_24h,
                        "sum": float(stats_24h.sum_24h)
                    },
                    "deposits_total": {
                        "count": total_stats.total_count,
                        "sum": float(total_stats.total_sum),
                        "pending": total_stats.pending_count
                    }
                }

        except Exception as e:
            logger.error(f"❌ Error getting monitoring stats: {e}")
            return {"error": str(e)}


# Глобальный экземпляр монитора
deposit_monitor = DepositMonitor()


async def start_deposit_monitoring():
    """Запустить мониторинг депозитов в фоне"""
    asyncio.create_task(deposit_monitor.start_monitoring())
    logger.info("🚀 Deposit monitoring task started")


async def stop_deposit_monitoring():
    """Остановить мониторинг депозитов"""
    await deposit_monitor.stop_monitoring()