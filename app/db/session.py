"""
Database session management.
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# Create async SQLAlchemy engine for application use
async_engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    echo=settings.DEBUG,
)

# Create sync engine for migrations and seeding
engine = create_engine(
    settings.DATABASE_URL.replace("+asyncpg", ""),  # Remove asyncpg for sync
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    echo=settings.DEBUG,
)

# Alias for backward compatibility
sync_engine = engine

# Create async SessionLocal class for application use
AsyncSessionLocal = async_sessionmaker(
    async_engine, class_=AsyncSession, expire_on_commit=False
)

# Create sync SessionLocal class for migrations and seeding
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)

# Create Base class for models
Base = declarative_base()


async def get_db():
    """Dependency to get async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


def get_sync_db():
    """Dependency to get sync database session (for migrations and seeding)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()