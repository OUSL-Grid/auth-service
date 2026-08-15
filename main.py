import asyncio

from src.db.session import get_db_session

# Ensure URL uses an async driver dialect like postgresql+asyncpg://
DB_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/mydb"

async def main():
    async with get_db_session(DB_URL) as session:
        # Example query execution
        # result = await session.execute(select(...))
        print("Session active:", session.is_active)

if __name__ == "__main__":
    asyncio.run(main())