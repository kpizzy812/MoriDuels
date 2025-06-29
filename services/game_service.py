"""
Сервис для игровой логики дуэлей
"""
import asyncio
import random
from decimal import Decimal
from typing import Optional, Dict, List
from datetime import datetime, timedelta

from database.models.user import User
from database.models.duel import Duel, DuelStatus, CoinSide
from database.models.transaction import Transaction, TransactionType
from services.solana_service import solana_service
from config.settings import HOUSE_ACCOUNTS, HOUSE_COMMISSION, MATCH_TIMEOUT
from utils.logger import setup_logger

logger = setup_logger(__name__)


class GameService:
    def __init__(self):
        self.waiting_players = {}  # {stake: [(user_id, timestamp), ...]}
        self.active_duels = {}  # {duel_id: duel_data}
        self.house_accounts = HOUSE_ACCOUNTS or ["@crypto_king", "@moon_trader", "@diamond_hands"]

    async def quick_match(self, user_id: int, stake: Decimal) -> Optional[Dict]:
        """Быстрый поиск игры"""
        try:
            # Проверяем баланс пользователя
            user = await User.get_by_telegram_id(user_id)
            if not user or user.balance < stake:
                return {"error": "Недостаточно средств"}

            # Снимаем ставку с баланса
            if not await user.subtract_balance(stake):
                return {"error": "Ошибка списания средств"}

            # Проверяем, есть ли ожидающие игроки с такой же ставкой
            if stake in self.waiting_players and self.waiting_players[stake]:
                # Находим оппонента
                opponent_data = self.waiting_players[stake].pop(0)
                opponent_id = opponent_data[0]

                # Проверяем, что оппонент все еще активен (не тот же игрок)
                if opponent_id != user_id:
                    opponent = await User.get_by_telegram_id(opponent_id)
                    if opponent and opponent.balance >= 0:  # Проверка что оппонент еще валиден
                        # Создаем дуэль между реальными игроками
                        duel = await self._create_real_duel(user_id, opponent_id, stake)
                        if duel:
                            return {
                                "type": "real_duel",
                                "duel_id": duel.id,
                                "opponent": opponent.username or f"Player {opponent_id}",
                                "stake": stake
                            }

            # Добавляем игрока в очередь ожидания
            if stake not in self.waiting_players:
                self.waiting_players[stake] = []

            self.waiting_players[stake].append((user_id, datetime.utcnow()))

            # Ждем MATCH_TIMEOUT секунд
            await asyncio.sleep(MATCH_TIMEOUT)

            # Проверяем, нашелся ли оппонент за это время
            if stake in self.waiting_players:
                # Удаляем игрока из очереди
                self.waiting_players[stake] = [
                    (uid, ts) for uid, ts in self.waiting_players[stake]
                    if uid != user_id
                ]

            # Создаем дуэль с ботом
            house_account = random.choice(self.house_accounts)
            duel = await self._create_house_duel(user_id, stake, house_account)

            if duel:
                return {
                    "type": "house_duel",
                    "duel_id": duel.id,
                    "opponent": house_account,
                    "stake": stake
                }

            # Если не удалось создать дуэль, возвращаем деньги
            await user.add_balance(stake)
            return {"error": "Не удалось создать игру"}

        except Exception as e:
            logger.error(f"❌ Error in quick_match for user {user_id}: {e}")
            return {"error": "Внутренняя ошибка"}

    async def _create_real_duel(self, player1_id: int, player2_id: int, stake: Decimal) -> Optional[Duel]:
        """Создать дуэль между реальными игроками"""
        try:
            # Создаем дуэль
            duel = await Duel.create_duel(player1_id, stake, is_house=False)
            await duel.add_player2(player2_id)

            # Создаем транзакции для ставок
            await Transaction.create_transaction(
                player1_id, TransactionType.DUEL_STAKE, stake, duel.id,
                description=f"Ставка в дуэли #{duel.id}"
            )
            await Transaction.create_transaction(
                player2_id, TransactionType.DUEL_STAKE, stake, duel.id,
                description=f"Ставка в дуэли #{duel.id}"
            )

            logger.info(f"✅ Created real duel {duel.id}: {player1_id} vs {player2_id}, stake: {stake}")
            return duel

        except Exception as e:
            logger.error(f"❌ Error creating real duel: {e}")
            return None

    async def _create_house_duel(self, player_id: int, stake: Decimal, house_account: str) -> Optional[Duel]:
        """Создать дуэль с ботом"""
        try:
            # Создаем дуэль с ботом
            duel = await Duel.create_duel(player_id, stake, is_house=True, house_account=house_account)

            # Эмулируем добавление бота как второго игрока
            await duel.add_player2(-1)  # -1 для бота

            # Создаем транзакцию для ставки игрока
            await Transaction.create_transaction(
                player_id, TransactionType.DUEL_STAKE, stake, duel.id,
                description=f"Ставка против {house_account}"
            )

            logger.info(f"✅ Created house duel {duel.id}: {player_id} vs {house_account}, stake: {stake}")
            return duel

        except Exception as e:
            logger.error(f"❌ Error creating house duel: {e}")
            return None

    async def flip_coin(self, duel_id: int, admin_decision: Optional[bool] = None) -> Optional[Dict]:
        """Бросок монеты"""
        try:
            duel = await Duel.get_by_id(duel_id)
            if not duel or duel.status != DuelStatus.ACTIVE:
                return {"error": "Дуэль не найдена или неактивна"}

            # Определяем результат
            if duel.is_house_duel and admin_decision is not None:
                # Админ решает исход для дуэли с ботом
                player_wins = admin_decision
            else:
                # Случайный результат для дуэлей между игроками
                player_wins = random.choice([True, False])

            # Определяем результат монеты и победителя
            coin_result = CoinSide.HEADS if player_wins else CoinSide.TAILS
            winner_id = duel.player1_id if player_wins else duel.player2_id

            # ИСПРАВЛЕННАЯ ЛОГИКА ВЫПЛАТ:
            # Победитель получает свою ставку + 70% от ставки оппонента
            if duel.is_house_duel:
                # Дуэль с ботом: игрок vs бот
                if player_wins:
                    # Игрок выиграл: своя ставка + 70% от ставки бота (равной ставке игрока)
                    winner_amount = duel.stake + (duel.stake * Decimal("0.7"))
                    commission = duel.stake * Decimal("0.3")  # 30% от ставки бота
                else:
                    # Бот выиграл: игрок ничего не получает
                    winner_amount = Decimal("0")
                    commission = duel.stake * Decimal("0.3")  # 30% от ставки игрока
            else:
                # Дуэль между игроками: обе ставки равны
                winner_amount = duel.stake + (duel.stake * Decimal("0.7"))  # своя + 70% от чужой
                commission = duel.stake * Decimal("0.3")  # 30% от ставки проигравшего

            # Завершаем дуэль
            await duel.finish_duel(winner_id, coin_result, winner_amount, commission)

            # Обновляем статистику игроков
            player1 = await User.get_by_telegram_id(duel.player1_id)
            if player1:
                await player1.update_game_stats(
                    won=(winner_id == duel.player1_id),
                    wagered=duel.stake,
                    won_amount=winner_amount if winner_id == duel.player1_id else Decimal(0)
                )

            if not duel.is_house_duel and duel.player2_id:
                player2 = await User.get_by_telegram_id(duel.player2_id)
                if player2:
                    await player2.update_game_stats(
                        won=(winner_id == duel.player2_id),
                        wagered=duel.stake,
                        won_amount=winner_amount if winner_id == duel.player2_id else Decimal(0)
                    )

            # Отправляем выигрыш победителю
            if winner_id > 0 and winner_amount > 0:  # Не бот и есть выигрыш
                await self._send_winnings(winner_id, winner_amount, duel_id)

            result = {
                "coin_result": coin_result.value,
                "winner_id": winner_id,
                "winner_amount": winner_amount,
                "commission": commission,
                "player1_id": duel.player1_id,
                "player2_id": duel.player2_id,
                "is_house_duel": duel.is_house_duel,
                "house_account": duel.house_account_name
            }

            logger.info(f"✅ Coin flipped for duel {duel_id}: {coin_result.value}, winner: {winner_id}, amount: {winner_amount}")
            return result

        except Exception as e:
            logger.error(f"❌ Error flipping coin for duel {duel_id}: {e}")
            return {"error": "Ошибка при броске монеты"}

    async def _send_winnings(self, user_id: int, amount: Decimal, duel_id: int) -> bool:
        """Отправить выигрыш игроку"""
        try:
            user = await User.get_by_telegram_id(user_id)
            if not user:
                logger.error(f"❌ User {user_id} not found for winnings")
                return False

            # Создаем транзакцию выигрыша
            transaction = await Transaction.create_transaction(
                user.id, TransactionType.DUEL_WIN, amount, duel_id,
                to_address=user.wallet_address,
                description=f"Выигрыш в дуэли #{duel_id}"
            )

            # Отправляем токены на кошелек
            tx_hash = await solana_service.send_token(
                user.wallet_address,
                amount,
                solana_service.mori_mint
            )

            if tx_hash:
                # Обновляем транзакцию
                await transaction.complete_transaction(tx_hash)
                logger.info(f"✅ Sent winnings {amount} MORI to user {user_id}")
                return True
            else:
                # Если не удалось отправить, добавляем на баланс
                await user.add_balance(amount)
                await transaction.fail_transaction("Ошибка отправки, добавлено на баланс")
                logger.warning(f"⚠️ Failed to send winnings, added to balance for user {user_id}")
                return False

        except Exception as e:
            logger.error(f"❌ Error sending winnings to user {user_id}: {e}")
            return False

    async def get_active_house_duels(self) -> List[Dict]:
        """Получить активные дуэли с ботами для админки"""
        try:
            # Получаем активные house дуэли из БД
            from database.connection import async_session
            from sqlalchemy import text

            async with async_session() as session:
                result = await session.execute(
                    text("""
                        SELECT * FROM duels 
                        WHERE status = 'active' AND is_house_duel = true 
                        ORDER BY created_at DESC
                    """)
                )

                duels = []
                for row in result.fetchall():
                    duel = Duel()
                    for key, value in row._mapping.items():
                        setattr(duel, key, value)
                    duels.append(duel)

                return duels

        except Exception as e:
            logger.error(f"❌ Error getting active house duels: {e}")
            return []

    async def cancel_duel(self, duel_id: int) -> bool:
        """Отменить дуэль"""
        try:
            duel = await Duel.get_by_id(duel_id)
            if not duel:
                return False

            # Возвращаем ставки игрокам
            if duel.player1_id:
                player1 = await User.get_by_telegram_id(duel.player1_id)
                if player1:
                    await player1.add_balance(duel.stake)

            if not duel.is_house_duel and duel.player2_id:
                player2 = await User.get_by_telegram_id(duel.player2_id)
                if player2:
                    await player2.add_balance(duel.stake)

            # Отменяем дуэль
            await duel.cancel_duel()
            logger.info(f"✅ Cancelled duel {duel_id}")
            return True

        except Exception as e:
            logger.error(f"❌ Error cancelling duel {duel_id}: {e}")
            return False

    async def cleanup_expired_waiting(self):
        """Очистка истекших ожиданий"""
        try:
            current_time = datetime.utcnow()
            timeout_threshold = timedelta(seconds=MATCH_TIMEOUT + 5)

            for stake in list(self.waiting_players.keys()):
                # Фильтруем устаревшие записи
                self.waiting_players[stake] = [
                    (user_id, timestamp) for user_id, timestamp in self.waiting_players[stake]
                    if current_time - timestamp < timeout_threshold
                ]

                # Удаляем пустые списки
                if not self.waiting_players[stake]:
                    del self.waiting_players[stake]

        except Exception as e:
            logger.error(f"❌ Error cleaning up expired waiting: {e}")


# Глобальный экземпляр сервиса
game_service = GameService()