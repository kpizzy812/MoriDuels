"""
Модель транзакций
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from enum import Enum as PyEnum

from sqlalchemy import Integer, String, DECIMAL, DateTime, ForeignKey, Enum, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.connection import Base, async_session
from utils.logger import setup_logger

logger = setup_logger(__name__)


class TransactionType(PyEnum):
    """Типы транзакций"""
    DEPOSIT = "deposit"  # Пополнение
    WITHDRAWAL = "withdrawal"  # Вывод
    DUEL_STAKE = "duel_stake"  # Ставка в дуэли
    DUEL_WIN = "duel_win"  # Выигрыш в дуэли
    COMMISSION = "commission"  # Комиссия


class TransactionStatus(PyEnum):
    """Статусы транзакций"""
    PENDING = "pending"  # В ожидании
    COMPLETED = "completed"  # Завершена
    FAILED = "failed"  # Не удалась
    CANCELLED = "cancelled"  # Отменена


class Transaction(Base):
    __tablename__ = "transactions"

    # Основные поля
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)

    # Данные транзакции
    type: Mapped[TransactionType] = mapped_column(Enum(TransactionType), nullable=False)
    amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False)
    status: Mapped[TransactionStatus] = mapped_column(Enum(TransactionStatus), default=TransactionStatus.PENDING)

    # Blockchain данные
    tx_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Хеш транзакции в Solana
    from_address: Mapped[Optional[str]] = mapped_column(String(44), nullable=True)
    to_address: Mapped[Optional[str]] = mapped_column(String(44), nullable=True)

    # Связанная дуэль (если есть)
    duel_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("duels.id"), nullable=True)

    # Метаданные
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)

    # Временные метки
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Связи
    user: Mapped["User"] = relationship("User", back_populates="transactions")
    duel: Mapped[Optional["Duel"]] = relationship("Duel", back_populates="transactions")

    @classmethod
    async def create_transaction(
            cls,
            user_id: int,
            transaction_type: TransactionType,
            amount: Decimal,
            duel_id: Optional[int] = None,
            tx_hash: Optional[str] = None,
            from_address: Optional[str] = None,
            to_address: Optional[str] = None,
            description: Optional[str] = None
    ) -> "Transaction":
        """Создать новую транзакцию"""
        async with async_session() as session:
            try:
                transaction = cls(
                    user_id=user_id,
                    type=transaction_type,
                    amount=amount,
                    duel_id=duel_id,
                    tx_hash=tx_hash,
                    from_address=from_address,
                    to_address=to_address,
                    description=description
                )
                session.add(transaction)
                await session.commit()
                await session.refresh(transaction)
                logger.info(f"✅ Created transaction: {transaction.id}, type: {transaction_type}")
                return transaction
            except Exception as e:
                await session.rollback()
                logger.error(f"❌ Error creating transaction: {e}")
                raise

    @classmethod
    async def get_by_id(cls, transaction_id: int) -> Optional["Transaction"]:
        """Получить транзакцию по ID"""
        async with async_session() as session:
            result = await session.execute(
                text("SELECT * FROM transactions WHERE id = :transaction_id"),
                {"transaction_id": transaction_id}
            )
            row = result.fetchone()
            if row:
                transaction = cls()
                for key, value in row._mapping.items():
                    setattr(transaction, key, value)
                return transaction
            return None

    @classmethod
    async def get_user_transactions(cls, user_id: int, limit: int = 50) -> list["Transaction"]:
        """Получить транзакции пользователя"""
        async with async_session() as session:
            result = await session.execute(
                text("""
                    SELECT * FROM transactions 
                    WHERE user_id = :user_id 
                    ORDER BY created_at DESC 
                    LIMIT :limit
                """),
                {"user_id": user_id, "limit": limit}
            )

            transactions = []
            for row in result.fetchall():
                transaction = cls()
                for key, value in row._mapping.items():
                    setattr(transaction, key, value)
                transactions.append(transaction)
            return transactions

    @classmethod
    async def get_pending_transactions(cls) -> list["Transaction"]:
        """Получить все ожидающие транзакции"""
        async with async_session() as session:
            result = await session.execute(
                text("SELECT * FROM transactions WHERE status = 'pending' ORDER BY created_at")
            )

            transactions = []
            for row in result.fetchall():
                transaction = cls()
                for key, value in row._mapping.items():
                    setattr(transaction, key, value)
                transactions.append(transaction)
            return transactions

    async def complete_transaction(self, tx_hash: str = None) -> bool:
        """Завершить транзакцию"""
        async with async_session() as session:
            try:
                self.status = TransactionStatus.COMPLETED
                self.completed_at = datetime.utcnow()
                if tx_hash:
                    self.tx_hash = tx_hash

                session.add(self)
                await session.commit()
                logger.info(f"✅ Completed transaction {self.id}")
                return True
            except Exception as e:
                await session.rollback()
                logger.error(f"❌ Error completing transaction {self.id}: {e}")
                return False

    async def fail_transaction(self, error_message: str) -> bool:
        """Пометить транзакцию как неудачную"""
        async with async_session() as session:
            try:
                self.status = TransactionStatus.FAILED
                self.error_message = error_message
                self.completed_at = datetime.utcnow()

                session.add(self)
                await session.commit()
                logger.info(f"❌ Failed transaction {self.id}: {error_message}")
                return True
            except Exception as e:
                await session.rollback()
                logger.error(f"❌ Error failing transaction {self.id}: {e}")
                return False

    def get_display_type(self) -> str:
        """Получить отображаемый тип транзакции"""
        type_names = {
            TransactionType.DEPOSIT: "💰 Пополнение",
            TransactionType.WITHDRAWAL: "💸 Вывод",
            TransactionType.DUEL_STAKE: "🎮 Ставка",
            TransactionType.DUEL_WIN: "🏆 Выигрыш",
            TransactionType.COMMISSION: "💼 Комиссия"
        }
        return type_names.get(self.type, str(self.type))

    def get_display_status(self) -> str:
        """Получить отображаемый статус"""
        status_names = {
            TransactionStatus.PENDING: "⏳ Ожидание",
            TransactionStatus.COMPLETED: "✅ Завершена",
            TransactionStatus.FAILED: "❌ Ошибка",
            TransactionStatus.CANCELLED: "🚫 Отменена"
        }
        return status_names.get(self.status, str(self.status))

    def __repr__(self):
        return f"<Transaction(id={self.id}, type={self.type}, amount={self.amount}, status={self.status})>"