"""
Модель дуэли
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from enum import Enum as PyEnum

from sqlalchemy import Integer, String, DECIMAL, DateTime, Boolean, ForeignKey, Enum, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.ext.asyncio import AsyncSession

from database.connection import Base, async_session
from utils.logger import setup_logger

logger = setup_logger(__name__)


class DuelStatus(PyEnum):
    """Статусы дуэли"""
    WAITING = "waiting"  # Ждет второго игрока
    ACTIVE = "active"  # Игра идет
    FINISHED = "finished"  # Завершена
    CANCELLED = "cancelled"  # Отменена


class CoinSide(PyEnum):
    """Стороны монеты"""
    HEADS = "heads"  # Орел
    TAILS = "tails"  # Решка


class Duel(Base):
    __tablename__ = "duels"

    # Основные поля
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Игроки
    player1_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    player2_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)

    # Игровые данные
    stake: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False)  # Ставка
    winner_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    coin_result: Mapped[Optional[CoinSide]] = mapped_column(Enum(CoinSide), nullable=True)

    # Выплаты
    winner_amount: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(20, 6), nullable=True)  # Выигрыш
    house_commission: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(20, 6), nullable=True)  # Комиссия

    # Статус и метаданные
    status: Mapped[DuelStatus] = mapped_column(Enum(DuelStatus), default=DuelStatus.WAITING)
    is_house_duel: Mapped[bool] = mapped_column(Boolean, default=False)  # Игра с ботом
    house_account_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Имя бота

    # Временные метки
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Связи
    player1: Mapped["User"] = relationship("User", foreign_keys=[player1_id], back_populates="duels_as_player1")
    player2: Mapped[Optional["User"]] = relationship("User", foreign_keys=[player2_id],
                                                     back_populates="duels_as_player2")
    winner: Mapped[Optional["User"]] = relationship("User", foreign_keys=[winner_id])
    transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="duel")

    @classmethod
    async def create_duel(cls, player1_id: int, stake: Decimal, is_house: bool = False,
                          house_account: str = None) -> "Duel":
        """Создать новую дуэль"""
        async with async_session() as session:
            try:
                duel = cls(
                    player1_id=player1_id,
                    stake=stake,
                    is_house_duel=is_house,
                    house_account_name=house_account
                )
                session.add(duel)
                await session.commit()
                await session.refresh(duel)
                logger.info(f"✅ Created new duel: {duel.id}, stake: {stake}")
                return duel
            except Exception as e:
                await session.rollback()
                logger.error(f"❌ Error creating duel: {e}")
                raise

    @classmethod
    async def get_by_id(cls, duel_id: int) -> Optional["Duel"]:
        """Получить дуэль по ID"""
        async with async_session() as session:
            result = await session.execute(
                text("SELECT * FROM duels WHERE id = :duel_id"),
                {"duel_id": duel_id}
            )
            row = result.fetchone()
            if row:
                duel = cls()
                for key, value in row._mapping.items():
                    setattr(duel, key, value)
                return duel
            return None

    @classmethod
    async def get_waiting_duels(cls, stake: Decimal = None) -> list["Duel"]:
        """Получить дуэли, ожидающие игроков"""
        async with async_session() as session:
            if stake:
                result = await session.execute(
                    text("SELECT * FROM duels WHERE status = 'waiting' AND stake = :stake ORDER BY created_at"),
                    {"stake": float(stake)}
                )
            else:
                result = await session.execute(
                    text("SELECT * FROM duels WHERE status = 'waiting' ORDER BY created_at")
                )

            duels = []
            for row in result.fetchall():
                duel = cls()
                for key, value in row._mapping.items():
                    setattr(duel, key, value)
                duels.append(duel)
            return duels

    async def add_player2(self, player2_id: int) -> bool:
        """Добавить второго игрока"""
        async with async_session() as session:
            try:
                self.player2_id = player2_id
                self.status = DuelStatus.ACTIVE
                self.started_at = datetime.utcnow()

                session.add(self)
                await session.commit()
                logger.info(f"✅ Added player2 to duel {self.id}")
                return True
            except Exception as e:
                await session.rollback()
                logger.error(f"❌ Error adding player2 to duel {self.id}: {e}")
                return False

    async def finish_duel(self, winner_id: int, coin_result: CoinSide, winner_amount: Decimal,
                          commission: Decimal) -> bool:
        """Завершить дуэль"""
        async with async_session() as session:
            try:
                self.winner_id = winner_id
                self.coin_result = coin_result
                self.winner_amount = winner_amount
                self.house_commission = commission
                self.status = DuelStatus.FINISHED
                self.finished_at = datetime.utcnow()

                session.add(self)
                await session.commit()
                logger.info(f"✅ Finished duel {self.id}, winner: {winner_id}")
                return True
            except Exception as e:
                await session.rollback()
                logger.error(f"❌ Error finishing duel {self.id}: {e}")
                return False

    async def cancel_duel(self) -> bool:
        """Отменить дуэль"""
        async with async_session() as session:
            try:
                self.status = DuelStatus.CANCELLED
                self.finished_at = datetime.utcnow()

                session.add(self)
                await session.commit()
                logger.info(f"✅ Cancelled duel {self.id}")
                return True
            except Exception as e:
                await session.rollback()
                logger.error(f"❌ Error cancelling duel {self.id}: {e}")
                return False

    def get_opponent_id(self, player_id: int) -> Optional[int]:
        """Получить ID оппонента"""
        if self.player1_id == player_id:
            return self.player2_id
        elif self.player2_id == player_id:
            return self.player1_id
        return None

    def is_player_in_duel(self, player_id: int) -> bool:
        """Проверить, участвует ли игрок в дуэли"""
        return player_id in [self.player1_id, self.player2_id]

    def __repr__(self):
        return f"<Duel(id={self.id}, stake={self.stake}, status={self.status})>"