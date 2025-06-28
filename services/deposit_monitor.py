"""
Сервис мониторинга депозитов
"""
import asyncio
from decimal import Decimal
from typing import Dict, Any
from datetime import datetime

from database.models.user import User
from database.models.transaction import Transaction, TransactionType
from services.solana_service import solana_service
from config.settings import BOT_WALLET_ADDRESS, MORI_TOKEN_MINT
from utils.logger import setup_logger

logger = setup_logger(__name__)


class DepositMonitor:
    def __init__(self):
        self.monitoring = False
        self.last_processed_signature = None

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

                # Ждем 30 секунд перед следующей проверкой
                await asyncio.sleep(30)

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
                limit=10,
                before=self.last_processed_signature
            )

            if not signatures_response.value:
                return

            # Обрабатываем новые транзакции
            new_signatures = []
            for sig_info in signatures_response.value:
                signature = str(sig_info.signature)

                # Пропускаем уже обработанные
                if signature == self.last_processed_signature:
                    break

                new_signatures.append(signature)

            # Обрабатываем в обратном порядке (от старых к новым)
            for signature in reversed(new_signatures):
                await self._process_transaction(signature)

            # Обновляем последнюю обработанную подпись
            if new_signatures:
                self.last_processed_signature = new_signatures[0]

        except Exception as e:
            logger.error(f"❌ Error checking new transactions: {e}")

    async def _process_transaction(self, signature: str):
        """Обработать транзакцию"""
        try:
            # Получаем детали транзакции
            tx_details = await solana_service.check_transaction(signature)

            if not tx_details or not tx_details.get("confirmed"):
                return

            # Получаем полную информацию о транзакции
            from solders.signature import Signature
            sig = Signature.from_string(signature)

            response = await solana_service.client.get_transaction(
                sig,
                commitment=solana_service.client._commitment
            )

            if not response.value:
                return

            transaction = response.value.transaction

            # Анализируем транзакцию на предмет депозитов MORI токенов
            deposit_info = await self._analyze_transaction_for_deposit(transaction, signature)

            if deposit_info:
                await self._process_deposit(deposit_info, signature)

        except Exception as e:
            logger.error(f"❌ Error processing transaction {signature}: {e}")

    async def _analyze_transaction_for_deposit(self, transaction, signature: str) -> Dict[str, Any]:
        """Анализировать транзакцию на предмет депозита"""
        try:
            # Здесь должен быть анализ SPL token transfer'ов
            # Это сложная логика парсинга транзакций Solana
            # Пока возвращаем заглушку

            # В реальной реализации нужно:
            # 1. Найти SPL Token Transfer инструкции
            # 2. Проверить, что токен = MORI_TOKEN_MINT
            # 3. Проверить, что получатель = BOT_WALLET_ADDRESS
            # 4. Извлечь отправителя и сумму

            logger.info(f"🔍 Analyzing transaction {signature} for deposits...")

            # Заглушка - в реальности здесь сложный парсинг
            return None

        except Exception as e:
            logger.error(f"❌ Error analyzing transaction: {e}")
            return None

    async def _process_deposit(self, deposit_info: Dict[str, Any], tx_hash: str):
        """Обработать депозит"""
        try:
            sender_address = deposit_info["sender"]
            amount = Decimal(str(deposit_info["amount"]))

            logger.info(f"💰 Processing deposit: {amount} MORI from {sender_address}")

            # Находим пользователя по адресу кошелька
            user = await self._find_user_by_wallet(sender_address)

            if not user:
                logger.warning(f"⚠️ No user found for wallet {sender_address}")
                return

            # Проверяем, не обработан ли уже этот депозит
            existing_tx = await self._check_existing_transaction(tx_hash)
            if existing_tx:
                logger.warning(f"⚠️ Transaction {tx_hash} already processed")
                return

            # Создаем транзакцию депозита
            transaction = await Transaction.create_transaction(
                user.id,
                TransactionType.DEPOSIT,
                amount,
                tx_hash=tx_hash,
                from_address=sender_address,
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

    async def _find_user_by_wallet(self, wallet_address: str) -> User:
        """Найти пользователя по адресу кошелька"""
        try:
            # В реальной реализации здесь был бы запрос к БД
            # SELECT * FROM users WHERE wallet_address = %s

            # Пока заглушка
            return None

        except Exception as e:
            logger.error(f"❌ Error finding user by wallet {wallet_address}: {e}")
            return None

    async def _check_existing_transaction(self, tx_hash: str) -> bool:
        """Проверить, существует ли транзакция с таким хешем"""
        try:
            # В реальной реализации:
            # SELECT COUNT(*) FROM transactions WHERE tx_hash = %s

            # Пока заглушка
            return False

        except Exception as e:
            logger.error(f"❌ Error checking existing transaction: {e}")
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


# Глобальный экземпляр монитора
deposit_monitor = DepositMonitor()


async def start_deposit_monitoring():
    """Запустить мониторинг депозитов в фоне"""
    asyncio.create_task(deposit_monitor.start_monitoring())
    logger.info("🚀 Deposit monitoring task started")


async def stop_deposit_monitoring():
    """Остановить мониторинг депозитов"""
    await deposit_monitor.stop_monitoring()