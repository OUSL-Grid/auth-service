from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import ConfigManager
from src.db.session import Database, get_db_session


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize and load configurations
    configs = ConfigManager()
    app.state.configs = configs.app_config
    app.state.settings = configs.settings

    # Initialize and database connection
    db_url = configs.settings.database_url_async
    db = await Database.get_instance(db_url)
    app.state.db = db

    yield

    # close database connection
    await Database.disconnect()


app = FastAPI(lifespan=lifespan)

def get_app_configs() -> ConfigManager:
    return app.state.configs

def get_app_settings() -> ConfigManager:
    return app.state.settings

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    # Pass empty string since singleton is already initialized in lifespan
    async with get_db_session("") as session:
        yield session

# define type aliases for dependencies
ConfigDep = Annotated[ConfigManager, Depends(get_app_configs)]
SettingsDep = Annotated[ConfigManager, Depends(get_app_settings)]
DbDep = Annotated[AsyncSession, Depends(get_db)]

# --- Routes ---
@app.get("/")
async def root(config: ConfigDep):
    return {"message": f"Welcome to {config.name}"}


@app.get("/health", status_code=status.HTTP_200_OK)
async def health(session: DbDep):
    try:
        # Execute lightweight ping to ensure pool is responding
        await session.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database unreachable: {e!s}"
        )