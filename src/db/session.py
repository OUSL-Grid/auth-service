import threading
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Optional

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


class Database:
    _instance: Optional["Database"] = None
    _lock: threading.Lock = threading.Lock()
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncGenerator]

    @classmethod
    async def get_instance(cls, db_url: str) -> "Database":
        # Async thread-safe Singleton initialization
        if cls._instance is None:
            with cls._lock:
                # Double-check locking pattern
                if cls._instance is None:
                    if not db_url:
                        raise ValueError(
                            "Database URL must be provided on first initialization."
                        )

                    instance = super().__new__(cls)

                    print("Initializing  Async SQLAlchemy Engine and SessionFactory...")
                    instance.engine = create_async_engine(
                        db_url,
                        pool_size=5,
                        max_overflow=10,
                        echo=False
                    )

                    instance.session_factory = async_sessionmaker(
                        bind=instance.engine,
                        autoflush=False,
                        expire_on_commit=False,
                        class_ = AsyncSession
                    )

                    cls._instance = instance

        return cls._instance

    @classmethod
    async def disconnect(cls) -> None:
        """ Close all connection in the pool and resets the singleton instance """
        if cls._instance is not None:
            with cls._lock:
                if cls._instance is not None:
                    print("Disposing Async SQLAlchemy Engine...")
                    await cls._instance.engine.dispose()
                    cls._instance = None


    def get_session(self) -> AsyncSession:
        """Creates a new AsyncSession from the session factory."""
        return self.session_factory()


@asynccontextmanager
async def get_db_session(db_url: str) -> AsyncGenerator[AsyncSession, None]:
    """ Async context manager for safely managing database sessions."""
    db = await Database.get_instance(db_url)
    session = db.get_session()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()