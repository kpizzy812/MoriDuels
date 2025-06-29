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

# SPL Token imports
from spl.token.instructions import (
    create_associated_token_account,
    get_associated_token_address,
    transfer_checked,
    TransferCheckedParams
)

from config.settings import SOLANA_RPC_URL, BOT_PRIVATE_KEY, BOT_WALLET_ADDRESS, MORI_TOKEN_MINT
from utils.logger import setup_logger

logger = setup_logger(__name__)


def validate_solana_address(address: str) -> bool:
    """Валидация Solana адреса"""
    try:
        if len(address) < 32 or len(address) > 44:
            return False
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
        self.token_decimals = 6  # Большинство SPL токенов используют 6 decimals

        # Инициализируем кошелек бота
        self._init_bot_wallet()

    def _init_bot_wallet(self):
        """Инициализация кошелька бота"""
        try:
            if BOT_PRIVATE_KEY:
                # Парсим приватный ключ (предполагаем формат base58)
                import base58
                private_key_bytes = base58.b58decode(BOT_PRIVATE_KEY)
                # Solana использует 64-байтные ключи, но Keypair.from_bytes ожидает первые 32 байта
                if len(private_key_bytes) == 64:
                    private_key_bytes = private_key_bytes[:32]
                elif len(private_key_bytes) != 32:
                    logger.error(f"❌ Invalid private key length: {len(private_key_bytes)}, expected 32 or 64 bytes")
                    return

                self.bot_keypair = Keypair.from_bytes(private_key_bytes)
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

    async def get_token_balance(self, address: str, token_mint: str = None) -> Optional[Decimal]:
        """Получить баланс токена"""
        try:
            pubkey = Pubkey.from_string(address)
            mint_pubkey = Pubkey.from_string(token_mint or str(self.mori_mint))

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

    async def get_token_decimals(self, token_mint: str) -> int:
        """Получить количество decimals токена"""
        try:
            mint_pubkey = Pubkey.from_string(token_mint)
            response = await self.client.get_account_info(mint_pubkey)

            if response.value and response.value.data:
                # Парсим данные mint аккаунта (decimals находится на позиции 44)
                data = response.value.data
                if len(data) > 44:
                    decimals = data[44]
                    return decimals

            # Fallback на стандартные 6 decimals
            return 6

        except Exception as e:
            logger.warning(f"⚠️ Could not get decimals for {token_mint}, using default 6: {e}")
            return 6

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
        """Отправить SPL токены"""
        try:
            if not self.bot_keypair:
                logger.error("❌ Bot keypair not initialized")
                return None

            mint_pubkey = Pubkey.from_string(token_mint or str(self.mori_mint))
            to_pubkey = Pubkey.from_string(to_address)

            # Получаем decimals токена
            decimals = await self.get_token_decimals(str(mint_pubkey))

            # Конвертируем amount с учетом decimals
            token_amount = int(amount * Decimal(10 ** decimals))

            # Получаем Associated Token Accounts
            from_ata = get_associated_token_address(self.bot_pubkey, mint_pubkey)
            to_ata = get_associated_token_address(to_pubkey, mint_pubkey)

            instructions = []

            # Проверяем, существует ли ATA получателя
            to_ata_info = await self.client.get_account_info(to_ata)
            if not to_ata_info.value:
                # Создаем ATA для получателя
                create_ata_ix = create_associated_token_account(
                    payer=self.bot_pubkey,
                    owner=to_pubkey,
                    mint=mint_pubkey
                )
                instructions.append(create_ata_ix)
                logger.info(f"📝 Creating ATA for {to_address[:8]}...")

            # Создаем инструкцию transfer
            transfer_ix = transfer_checked(
                TransferCheckedParams(
                    program_id=Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"),  # SPL Token Program
                    source=from_ata,
                    mint=mint_pubkey,
                    dest=to_ata,
                    owner=self.bot_pubkey,
                    amount=token_amount,
                    decimals=decimals
                )
            )
            instructions.append(transfer_ix)

            # Получаем последний blockhash
            recent_blockhash = await self.client.get_latest_blockhash()

            # Создаем и подписываем транзакцию
            transaction = Transaction.new_with_payer(
                instructions,
                self.bot_pubkey
            )
            transaction.sign([self.bot_keypair], recent_blockhash.value.blockhash)

            # Отправляем транзакцию
            result = await self.client.send_transaction(
                transaction,
                opts=TxOpts(skip_preflight=False)  # Включаем preflight для SPL транзакций
            )

            if result.value:
                tx_hash = str(result.value)
                logger.info(f"✅ Sent {amount} tokens to {to_address[:8]}... TX: {tx_hash[:8]}...")
                return tx_hash

            logger.error("❌ Failed to send token transaction")
            return None

        except Exception as e:
            logger.error(f"❌ Error sending tokens to {to_address}: {e}")
            return None

    async def check_transaction(self, tx_hash: str) -> Optional[Dict[str, Any]]:
        """Проверить статус транзакции"""
        try:
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

    async def parse_token_transfer(self, tx_hash: str) -> Optional[Dict[str, Any]]:
        """Парсинг SPL token transfer из транзакции"""
        try:
            from solders.signature import Signature
            signature = Signature.from_string(tx_hash)

            response = await self.client.get_transaction(
                signature,
                commitment=Confirmed
            )

            if not response.value or not response.value.transaction.meta:
                return None

            meta = response.value.transaction.meta

            # Ищем изменения в токен аккаунтах
            pre_token_balances = meta.pre_token_balances or []
            post_token_balances = meta.post_token_balances or []

            for pre_balance in pre_token_balances:
                # Находим соответствующий post balance
                post_balance = None
                for pb in post_token_balances:
                    if pb.account_index == pre_balance.account_index:
                        post_balance = pb
                        break

                if post_balance and pre_balance.mint == str(self.mori_mint):
                    # Рассчитываем изменение
                    pre_amount = Decimal(pre_balance.ui_token_amount.amount)
                    post_amount = Decimal(post_balance.ui_token_amount.amount)

                    if post_amount > pre_amount:
                        # Это пополнение
                        amount = (post_amount - pre_amount) / Decimal(10 ** post_balance.ui_token_amount.decimals)

                        # Получаем адрес владельца аккаунта
                        account_info = response.value.transaction.transaction.message.account_keys[pre_balance.account_index]

                        return {
                            "type": "deposit",
                            "amount": amount,
                            "token_mint": pre_balance.mint,
                            "account": str(account_info),
                            "decimals": post_balance.ui_token_amount.decimals
                        }

            return None

        except Exception as e:
            logger.error(f"❌ Error parsing token transfer {tx_hash}: {e}")
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
                await asyncio.sleep(30)  # Проверяем каждые 30 секунд

                # Получаем новые подписи
                new_signatures_response = await self.client.get_signatures_for_address(
                    pubkey,
                    before=last_signature,
                    commitment=Confirmed
                )

                if new_signatures_response.value:
                    for sig_info in reversed(new_signatures_response.value):
                        # Парсим транзакцию на предмет токен трансферов
                        transfer_info = await self.parse_token_transfer(str(sig_info.signature))
                        if transfer_info:
                            await callback_func(address, str(sig_info.signature), transfer_info)

                    # Обновляем последнюю подпись
                    last_signature = new_signatures_response.value[0].signature

        except Exception as e:
            logger.error(f"❌ Error monitoring address {address}: {e}")

    async def get_recent_token_transactions(self, address: str, limit: int = 10) -> list:
        """Получить последние токен транзакции"""
        try:
            pubkey = Pubkey.from_string(address)

            signatures_response = await self.client.get_signatures_for_address(
                pubkey,
                limit=limit,
                commitment=Confirmed
            )

            transactions = []
            if signatures_response.value:
                for sig_info in signatures_response.value:
                    transfer_info = await self.parse_token_transfer(str(sig_info.signature))
                    if transfer_info:
                        transactions.append({
                            "signature": str(sig_info.signature),
                            "block_time": sig_info.block_time,
                            **transfer_info
                        })

            return transactions

        except Exception as e:
            logger.error(f"❌ Error getting recent transactions for {address}: {e}")
            return []

    async def validate_token_mint_info(self, token_mint: str) -> Dict[str, Any]:
        """Получить информацию о токен mint"""
        try:
            mint_pubkey = Pubkey.from_string(token_mint)
            response = await self.client.get_account_info(mint_pubkey)

            if response.value and response.value.data:
                data = response.value.data

                # Парсим основные данные mint аккаунта
                # Структура: https://docs.rs/spl-token/latest/spl_token/state/struct.Mint.html
                if len(data) >= 82:
                    supply_bytes = data[36:44]
                    decimals = data[44]

                    supply = int.from_bytes(supply_bytes, 'little')

                    return {
                        "valid": True,
                        "supply": supply,
                        "decimals": decimals,
                        "supply_ui": supply / (10 ** decimals)
                    }

            return {"valid": False, "error": "Invalid mint account"}

        except Exception as e:
            logger.error(f"❌ Error validating token mint {token_mint}: {e}")
            return {"valid": False, "error": str(e)}

    async def close(self):
        """Закрыть соединение"""
        await self.client.close()


# Глобальный экземпляр сервиса
solana_service = SolanaService()