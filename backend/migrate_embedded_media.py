import asyncio

from database import AsyncSessionLocal, engine
from services.media_migration import migrate_embedded_assets


async def main() -> None:
    async with AsyncSessionLocal() as db:
        print(await migrate_embedded_assets(db))
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
