"""
Модель пользователя
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import BigInteger, String, DECIMAL, Integer, DateTime, Boolean, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.ext.asyncio import AsyncSession

from database.connection import Base, async_session
from utils.logger import setup_logger

logger = setup_logger(__name__)


class User(Base):
    __tablename__ = "users"

    # Основные поля
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    wallet_address: Mapped[str] = mapped_column(String(44), nullable=False)  # Solana адрес

    # Игровая статистика
    balance: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), default=0)
    total_games: Mapped[int] = mapped_column(Integer, default=0)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    total_wagered: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), default=0)
    total_won: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), default=0)

    # Системные поля
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    wallet_updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Связи
    duels_as_player1: Mapped[List["Duel"]] = relationship("Duel", foreign_keys="Duel.player1_id",
                                                          back_populates="player1")
    duels_as_player2: Mapped[List["Duel"]] = relationship("Duel", foreign_keys="Duel.player2_id",
                                                          back_populates="player2")
    transactions: Mapped[List["Transaction"]] = relationship("Transaction", back_populates="user")
    rooms_created: Mapped[List["Room"]] = relationship("Room", back_populates="creator")

    @classmethod
    async def get_by_telegram_id(cls, telegram_id: int) -> Optional["User"]:
        """Получить пользователя по Telegram ID"""
        async with async_session() as session:
            result = await session.execute(
                text("SELECT * FROM users WHERE telegram_id = :telegram_id"),
                {"telegram_id": telegram_id}
            )
            row = result.fetchone()
            if row:
                user = cls()
                for key, value in row._mapping.items():
                    setattr(user, key, value)
                return user
            return None

    @classmethod
    async def create_user(cls, telegram_id: int, wallet_address: str, username: str = None) -> "User":
        """Создать нового пользователя"""
        async with async_session() as session:
            try:
                user = cls(
                    telegram_id=telegram_id,
                    username=username,
                    wallet_address=wallet_address
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)
                logger.info(f"✅ Created new user: {telegram_id}")
                return user
            except Exception as e:
                await session.rollback()
                logger.error(f"❌ Error creating user {telegram_id}: {e}")
                raise

    async def update_wallet(self, new_wallet_address: str) -> bool:
        """Обновить адрес кошелька"""
        async with async_session() as session:
            try:
                # Записываем в историю смены кошельков
                from database.models.wallet_history import WalletHistory
                history = WalletHistory(
                    user_id=self.id,
                    old_address=self.wallet_address,
                    new_address=new_wallet_address
                )
                session.add(history)

                # Обновляем кошелек
                self.wallet_address = new_wallet_address
                self.wallet_updated_at = datetime.utcnow()

                session.add(self)
                await session.commit()
                logger.info(f"✅ Updated wallet for user {self.telegram_id}")
                return True
            except Exception as e:
                await session.rollback()
                logger.error(f"❌ Error updating wallet for user {self.telegram_id}: {e}")
                return False

    async def add_balance(self, amount: Decimal) -> bool:
        """Добавить к балансу"""
        async with async_session() as session:
            try:
                self.balance += amount
                session.add(self)
                await session.commit()
                logger.info(f"✅ Added {amount} to balance of user {self.telegram_id}")
                return True
            except Exception as e:
                await session.rollback()
                logger.error(f"❌ Error adding balance to user {self.telegram_id}: {e}")
                return False

    async def subtract_balance(self, amount: Decimal) -> bool:
        """Снять с баланса"""
        if self.balance < amount:
            logger.warning(f"⚠️ Insufficient balance for user {self.telegram_id}: {self.balance} < {amount}")
            return False

        async with async_session() as session:
            try:
                self.balance -= amount
                session.add(self)
                await session.commit()
                logger.info(f"✅ Subtracted {amount} from balance of user {self.telegram_id}")
                return True
            except Exception as e:
                await session.rollback()
                logger.error(f"❌ Error subtracting balance from user {self.telegram_id}: {e}")
                return False

    async def update_game_stats(self, won: bool, wagered: Decimal, won_amount: Decimal = None) -> bool:
        """Обновить игровую статистику"""
        async with async_session() as session:
            try:
                self.total_games += 1
                self.total_wagered += wagered

                if won:
                    self.wins += 1
                    if won_amount:
                        self.total_won += won_amount

                session.add(self)
                await session.commit()
                logger.info(f"✅ Updated game stats for user {self.telegram_id}")
                return True
            except Exception as e:
                await session.rollback()
                logger.error(f"❌ Error updating game stats for user {self.telegram_id}: {e}")
                return False

    def get_win_rate(self) -> float:
        """Получить процент побед"""
        if self.total_games == 0:
            return 0.0
        return (self.wins / self.total_games) * 100

    def get_profit(self) -> Decimal:
        """Получить общую прибыль/убыток"""
        return self.total_won - self.total_wagered

    def __repr__(self):
        return f"<User(id={self.id}, telegram_id={self.telegram_id}, balance={self.balance})>"