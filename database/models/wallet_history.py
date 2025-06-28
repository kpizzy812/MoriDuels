"""
Модель истории смены кошельков
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, String, DateTime, ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.connection import Base, async_session
from utils.logger import setup_logger

logger = setup_logger(__name__)


class WalletHistory(Base):
    __tablename__ = "wallet_history"

    # Основные поля
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)

    # Адреса
    old_address: Mapped[Optional[str]] = mapped_column(String(44),
                                                       nullable=True)  # Старый адрес (может быть None при первой привязке)
    new_address: Mapped[str] = mapped_column(String(44), nullable=False)  # Новый адрес

    # Временная метка
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Связи
    user: Mapped["User"] = relationship("User")

    @classmethod
    async def create_history_record(cls, user_id: int, old_address: Optional[str], new_address: str) -> "WalletHistory":
        """Создать запись в истории"""
        async with async_session() as session:
            try:
                history = cls(
                    user_id=user_id,
                    old_address=old_address,
                    new_address=new_address
                )
                session.add(history)
                await session.commit()
                await session.refresh(history)
                logger.info(f"✅ Created wallet history record for user {user_id}")
                return history
            except Exception as e:
                await session.rollback()
                logger.error(f"❌ Error creating wallet history: {e}")
                raise

    @classmethod
    async def get_user_history(cls, user_id: int, limit: int = 10) -> list["WalletHistory"]:
        """Получить историю смены кошельков пользователя"""
        async with async_session() as session:
            result = await session.execute(
                text("""
                    SELECT * FROM wallet_history 
                    WHERE user_id = :user_id 
                    ORDER BY changed_at DESC 
                    LIMIT :limit
                """),
                {"user_id": user_id, "limit": limit}
            )

            history_records = []
            for row in result.fetchall():
                record = cls()
                for key, value in row._mapping.items():
                    setattr(record, key, value)
                history_records.append(record)
            return history_records

    def get_display_change(self) -> str:
        """Получить отображаемое описание изменения"""
        if self.old_address:
            return f"Изменен с {self.old_address[:8]}...{self.old_address[-4:]} на {self.new_address[:8]}...{self.new_address[-4:]}"
        else:
            return f"Привязан кошелек {self.new_address[:8]}...{self.new_address[-4:]}"

    def __repr__(self):
        return f"<WalletHistory(id={self.id}, user_id={self.user_id}, changed_at={self.changed_at})>"