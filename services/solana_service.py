"""
Сервис для работы с Solana блокчейном
"""
import asyncio
from decimal import Decimal
from typing import Optional, Dict, Any

from solders.pubkey import Pubkey
from solders.keypair import Keypair
from solders.transaction import Transaction
from solders.system_program import TransferParams, transfer
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed
from solana.rpc.types import TxOpts

from config.settings import SOLANA_RPC_URL, BOT_PRIVATE_KEY, BOT_WALLET_ADDRESS, MORI_TOKEN_MINT
from utils.logger import setup_logger

logger = setup_logger(__name__)


def validate_solana_address(address: str) -> bool:
    """Валидация Solana адреса"""
    try:
        Pubkey.from_string(address)
        return True
    except Exception:
        return False


class SolanaService:
    def __init__(self):
        self.client = AsyncClient(SOLANA_RPC_URL)
        self.bot_keypair = None
        self.bot_pubkey = None
        self.mori_mint = None

        # Инициализируем кошелек бота
        self._init_bot_wallet()

    def _init_bot_wallet(self):
        """Инициализация кошелька бота"""
        try:
            if BOT_PRIVATE_KEY:
                # Парсим приватный ключ (предполагаем формат base58)
                import base58
                private_key_bytes = base58.b58decode(BOT_PRIVATE_KEY)
                self.bot_keypair = Keypair.from_bytes(private_key_bytes[:32])
                self.bot_pubkey = self.bot_keypair.pubkey()
                logger.info(f"✅ Bot wallet initialized: {str(self.bot_pubkey)[:8]}...")

            if MORI_TOKEN_MINT:
                self.mori_mint = Pubkey.from_string(MORI_TOKEN_MINT)
                logger.info(f"✅ MORI token mint: {str(self.mori_mint)[:8]}...")

        except Exception as e:
            logger.error(f"❌ Error initializing bot wallet: {e}")

    async def get_sol_balance(self, address: str) -> Optional[Decimal]:
        """Получить баланс SOL"""
        try:
            pubkey = Pubkey.from_string(address)
            response = await self.client.get_balance(pubkey, commitment=Confirmed)

            if response.value is not None:
                # Конвертируем из lamports в SOL
                sol_balance = Decimal(response.value) / Decimal(10 ** 9)
                return sol_balance
            return None

        except Exception as e:
            logger.error(f"❌ Error getting SOL balance for {address}: {e}")
            return None

    async def get_token_balance(self, address: str, token_mint: str) -> Optional[Decimal]:
        """Получить баланс токена"""
        try:
            pubkey = Pubkey.from_string(address)
            mint_pubkey = Pubkey.from_string(token_mint)

            # Получаем токен аккаунты
            response = await self.client.get_token_accounts_by_owner(
                pubkey,
                {"mint": mint_pubkey},
                commitment=Confirmed
            )

            if response.value:
                # Берем первый токен аккаунт
                token_account = response.value[0]
                account_pubkey = Pubkey.from_string(token_account.pubkey)

                # Получаем баланс токена
                balance_response = await self.client.get_token_account_balance(
                    account_pubkey,
                    commitment=Confirmed
                )

                if balance_response.value:
                    # Учитываем decimals токена
                    amount = balance_response.value.amount
                    decimals = balance_response.value.decimals
                    token_balance = Decimal(amount) / Decimal(10 ** decimals)
                    return token_balance

            return Decimal(0)

        except Exception as e:
            logger.error(f"❌ Error getting token balance for {address}: {e}")
            return None

    async def send_sol(self, to_address: str, amount: Decimal) -> Optional[str]:
        """Отправить SOL"""
        try:
            if not self.bot_keypair:
                logger.error("❌ Bot keypair not initialized")
                return None

            to_pubkey = Pubkey.from_string(to_address)
            lamports = int(amount * Decimal(10 ** 9))  # Конвертируем в lamports

            # Создаем транзакцию
            transfer_ix = transfer(
                TransferParams(
                    from_pubkey=self.bot_pubkey,
                    to_pubkey=to_pubkey,
                    lamports=lamports
                )
            )

            # Получаем последний blockhash
            recent_blockhash = await self.client.get_latest_blockhash()

            # Создаем и подписываем транзакцию
            transaction = Transaction.new_with_payer(
                [transfer_ix],
                self.bot_pubkey
            )
            transaction.sign([self.bot_keypair], recent_blockhash.value.blockhash)

            # Отправляем транзакцию
            result = await self.client.send_transaction(
                transaction,
                opts=TxOpts(skip_preflight=True)
            )

            if result.value:
                tx_hash = str(result.value)
                logger.info(f"✅ SOL sent: {amount} to {to_address[:8]}... TX: {tx_hash[:8]}...")
                return tx_hash

            return None

        except Exception as e:
            logger.error(f"❌ Error sending SOL to {to_address}: {e}")
            return None

    async def send_token(self, to_address: str, amount: Decimal, token_mint: str = None) -> Optional[str]:
        """Отправить токены"""
        try:
            if not self.bot_keypair:
                logger.error("❌ Bot keypair not initialized")
                return None

            mint = token_mint or str(self.mori_mint)
            if not mint:
                logger.error("❌ Token mint not specified")
                return None

            # ВРЕМЕННАЯ ЗАГЛУШКА - для демонстрации
            # В реальности здесь должна быть логика отправки SPL токенов:
            # 1. Поиск Associated Token Accounts
            # 2. Создание ATA если не существует
            # 3. Создание transfer инструкции для SPL токена

            logger.warning(f"⚠️ Token transfer mock: {amount} MORI to {to_address[:8]}...")

            # Имитируем задержку сети
            await asyncio.sleep(1)

            # Возвращаем фейковый хеш транзакции
            import hashlib
            import time
            mock_data = f"{to_address}{amount}{time.time()}"
            mock_hash = hashlib.sha256(mock_data.encode()).hexdigest()

            logger.info(f"✅ Mock token transfer completed: TX {mock_hash[:16]}...")
            return mock_hash

        except Exception as e:
            logger.error(f"❌ Error sending tokens to {to_address}: {e}")
            return None

    async def check_transaction(self, tx_hash: str) -> Optional[Dict[str, Any]]:
        """Проверить статус транзакции"""
        try:
            # Если это mock транзакция (хеш длиннее 64 символов), возвращаем "подтверждено"
            if len(tx_hash) == 64 and tx_hash.startswith(('a', 'b', 'c', 'd', 'e', 'f')):
                return {
                    "confirmed": True,
                    "slot": 12345678,
                    "block_time": 1640995200,
                    "fee": 5000
                }

            from solders.signature import Signature
            signature = Signature.from_string(tx_hash)

            response = await self.client.get_transaction(
                signature,
                commitment=Confirmed
            )

            if response.value:
                return {
                    "confirmed": True,
                    "slot": response.value.slot,
                    "block_time": response.value.block_time,
                    "fee": response.value.transaction.meta.fee if response.value.transaction.meta else 0
                }

            return {"confirmed": False}

        except Exception as e:
            logger.error(f"❌ Error checking transaction {tx_hash}: {e}")
            return None

    async def monitor_address_for_deposits(self, address: str, callback_func) -> None:
        """Мониторинг адреса для депозитов"""
        try:
            pubkey = Pubkey.from_string(address)

            # Получаем текущую подпись для отслеживания новых транзакций
            signatures_response = await self.client.get_signatures_for_address(
                pubkey,
                limit=1,
                commitment=Confirmed
            )

            last_signature = None
            if signatures_response.value:
                last_signature = signatures_response.value[0].signature

            logger.info(f"🔍 Started monitoring {address[:8]}... for deposits")

            while True:
                await asyncio.sleep(10)  # Проверяем каждые 10 секунд

                # Получаем новые подписи
                new_signatures_response = await self.client.get_signatures_for_address(
                    pubkey,
                    before=last_signature,
                    commitment=Confirmed
                )

                if new_signatures_response.value:
                    for sig_info in reversed(new_signatures_response.value):
                        # Получаем детали транзакции
                        tx_details = await self.check_transaction(str(sig_info.signature))
                        if tx_details and tx_details.get("confirmed"):
                            await callback_func(address, str(sig_info.signature), tx_details)

                    # Обновляем последнюю подпись
                    last_signature = new_signatures_response.value[0].signature

        except Exception as e:
            logger.error(f"❌ Error monitoring address {address}: {e}")

    async def close(self):
        """Закрыть соединение"""
        await self.client.close()


# Глобальный экземпляр сервиса
solana_service = SolanaService()