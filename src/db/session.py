import threading
from contextlib import contextmanager
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


class Database:
    _instance: Optional["Database"] = None
    _lock: threading.Lock = threading.Lock()
    engine: Engine
    session_factory: sessionmaker

    def __new__(cls, db_url: str) -> "Database":
        # Thread-safe Singleton initialization
        if cls._instance is None:
            with cls._lock:
                # Double-check locking pattern
                if cls._instance is None:
                    if not db_url:
                        raise ValueError(
                            "Database URL must be provided on first initialization."
                        )

                    instance = super().__new__(cls)

                    print("Initializing SQLAlchemy Engine and SessionFactory...")
                    instance.engine = create_engine(
                        db_url,
                        pool_size=5,
                        max_overflow=10,
                        echo=False
                    )

                    instance.session_factory = sessionmaker(
                        bind=instance.engine,
                        autoflush=False,
                        expire_on_commit=False
                    )

                    cls._instance = instance

        return cls._instance

    def get_session(self) -> Session:
        """Creates a new session from the session factory."""
        return self.session_factory()


@contextmanager
def get_db_session(db_url: str):
    """Context manager for safely managing database sessions."""
    db = Database(db_url)
    session = db.get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()