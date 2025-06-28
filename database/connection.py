"""
Подключение к базе данных PostgreSQL
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from config.settings import DATABASE_URL
from utils.logger import setup_logger

logger = setup_logger(__name__)


class Base(DeclarativeBase):
    """Базовый класс для всех моделей"""
    pass


# Создаем движок базы данных
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Поставить True для логирования SQL запросов
    future=True
)

# Создаем фабрику сессий
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def get_session():
    """Получение сессии базы данных"""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            await session.close()


async def init_db():
    """Инициализация базы данных - создание таблиц"""
    try:
        async with engine.begin() as conn:
            # Импортируем все модели для создания таблиц
            from database.models.user import User
            from database.models.duel import Duel
            from database.models.transaction import Transaction
            from database.models.room import Room

            # Создаем все таблицы
            await conn.run_sync(Base.metadata.create_all)
            logger.info("✅ Database tables created successfully")

    except Exception as e:
        logger.error(f"❌ Error creating database tables: {e}")
        raise


async def close_db():
    """Закрытие соединения с базой данных"""
    await engine.dispose()
    logger.info("🔒 Database connection closed")
