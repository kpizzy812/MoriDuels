"""
Модель игровой комнаты
"""
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional
from enum import Enum as PyEnum

from sqlalchemy import Integer, String, DECIMAL, DateTime, Boolean, ForeignKey, Enum, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.connection import Base, async_session
from utils.logger import setup_logger

logger = setup_logger(__name__)


class RoomStatus(PyEnum):
    """Статусы комнаты"""
    WAITING = "waiting"  # Ждет игроков
    FULL = "full"  # Полная (2 игрока)
    EXPIRED = "expired"  # Истекло время ожидания
    CLOSED = "closed"  # Закрыта создателем


class Room(Base):
    __tablename__ = "rooms"

    # Основные поля
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    room_code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)  # Короткий код комнаты

    # Создатель и игра
    creator_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    stake: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False)

    # Статус
    status: Mapped[RoomStatus] = mapped_column(Enum(RoomStatus), default=RoomStatus.WAITING)
    is_private: Mapped[bool] = mapped_column(Boolean, default=False)  # Приватная комната

    # Связанная дуэль (когда комната заполнится)
    duel_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("duels.id"), nullable=True)

    # Временные ограничения
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)  # Когда истекает
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Связи
    creator: Mapped["User"] = relationship("User", back_populates="rooms_created")
    duel: Mapped[Optional["Duel"]] = relationship("Duel")

    @classmethod
    async def create_room(cls, creator_id: int, stake: Decimal, is_private: bool = False,
                          expires_in_minutes: int = 5) -> "Room":
        """Создать новую комнату"""
        async with async_session() as session:
            try:
                # Генерируем уникальный код комнаты
                room_code = await cls._generate_room_code()
                expires_at = datetime.utcnow() + timedelta(minutes=expires_in_minutes)

                room = cls(
                    room_code=room_code,
                    creator_id=creator_id,
                    stake=stake,
                    is_private=is_private,
                    expires_at=expires_at
                )
                session.add(room)
                await session.commit()
                await session.refresh(room)
                logger.info(f"✅ Created room: {room.room_code}, stake: {stake}")
                return room
            except Exception as e:
                await session.rollback()
                logger.error(f"❌ Error creating room: {e}")
                raise

    @classmethod
    async def get_by_code(cls, room_code: str) -> Optional["Room"]:
        """Получить комнату по коду"""
        async with async_session() as session:
            result = await session.execute(
                text("SELECT * FROM rooms WHERE room_code = :room_code"),
                {"room_code": room_code}
            )
            row = result.fetchone()
            if row:
                room = cls()
                for key, value in row._mapping.items():
                    setattr(room, key, value)
                return room
            return None

    @classmethod
    async def get_active_rooms(cls, limit: int = 20) -> list["Room"]:
        """Получить активные комнаты"""
        async with async_session() as session:
            result = await session.execute(
                text("""
                    SELECT * FROM rooms 
                    WHERE status = 'waiting' AND expires_at > NOW() 
                    ORDER BY created_at DESC 
                    LIMIT :limit
                """),
                {"limit": limit}
            )

            rooms = []
            for row in result.fetchall():
                room = cls()
                for key, value in row._mapping.items():
                    setattr(room, key, value)
                rooms.append(room)
            return rooms

    @classmethod
    async def cleanup_expired_rooms(cls) -> int:
        """Очистить истекшие комнаты"""
        async with async_session() as session:
            try:
                result = await session.execute(
                    text("""
                        UPDATE rooms 
                        SET status = 'expired', closed_at = NOW() 
                        WHERE status = 'waiting' AND expires_at < NOW()
                    """)
                )
                await session.commit()
                count = result.rowcount
                logger.info(f"✅ Cleaned up {count} expired rooms")
                return count
            except Exception as e:
                await session.rollback()
                logger.error(f"❌ Error cleaning up expired rooms: {e}")
                return 0

    @classmethod
    async def _generate_room_code(cls) -> str:
        """Генерировать уникальный код комнаты"""
        import random
        import string

        while True:
            # Генерируем 6-символьный код
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

            # Проверяем уникальность
            async with async_session() as session:
                result = await session.execute(
                    text("SELECT COUNT(*) FROM rooms WHERE room_code = :code"),
                    {"code": code}
                )
                count = result.scalar()
                if count == 0:
                    return code

    async def join_room(self, player_id: int) -> Optional["Duel"]:
        """Присоединиться к комнате"""
        if self.status != RoomStatus.WAITING:
            logger.warning(f"⚠️ Cannot join room {self.room_code}: status is {self.status}")
            return None

        if self.creator_id == player_id:
            logger.warning(f"⚠️ Creator cannot join their own room {self.room_code}")
            return None

        if datetime.utcnow() > self.expires_at:
            logger.warning(f"⚠️ Room {self.room_code} has expired")
            await self.expire_room()
            return None

        async with async_session() as session:
            try:
                # Создаем дуэль
                from database.models.duel import Duel
                duel = await Duel.create_duel(self.creator_id, self.stake)
                await duel.add_player2(player_id)

                # Обновляем комнату
                self.status = RoomStatus.FULL
                self.duel_id = duel.id
                self.closed_at = datetime.utcnow()

                session.add(self)
                await session.commit()

                logger.info(f"✅ Player {player_id} joined room {self.room_code}")
                return duel
            except Exception as e:
                await session.rollback()
                logger.error(f"❌ Error joining room {self.room_code}: {e}")
                return None

    async def close_room(self) -> bool:
        """Закрыть комнату"""
        async with async_session() as session:
            try:
                self.status = RoomStatus.CLOSED
                self.closed_at = datetime.utcnow()

                session.add(self)
                await session.commit()
                logger.info(f"✅ Closed room {self.room_code}")
                return True
            except Exception as e:
                await session.rollback()
                logger.error(f"❌ Error closing room {self.room_code}: {e}")
                return False

    async def expire_room(self) -> bool:
        """Пометить комнату как истекшую"""
        async with async_session() as session:
            try:
                self.status = RoomStatus.EXPIRED
                self.closed_at = datetime.utcnow()

                session.add(self)
                await session.commit()
                logger.info(f"✅ Expired room {self.room_code}")
                return True
            except Exception as e:
                await session.rollback()
                logger.error(f"❌ Error expiring room {self.room_code}: {e}")
                return False

    def is_expired(self) -> bool:
        """Проверить, истекла ли комната"""
        return datetime.utcnow() > self.expires_at

    def get_time_left(self) -> timedelta:
        """Получить оставшееся время"""
        if self.is_expired():
            return timedelta(0)
        return self.expires_at - datetime.utcnow()

    def get_share_link(self, bot_username: str) -> str:
        """Получить ссылку для приглашения"""
        return f"https://t.me/{bot_username}?start=room_{self.room_code}"

    def __repr__(self):
        return f"<Room(code={self.room_code}, stake={self.stake}, status={self.status})>"