"""
DC Monitoring Simulator - Conexión a Base de Datos
SQLite asíncrono con SQLAlchemy
"""
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from .models import Base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data/simulator.db")

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False}
)

AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def init_db():
    """Crear todas las tablas al iniciar."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    """Dependency injection para FastAPI."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
