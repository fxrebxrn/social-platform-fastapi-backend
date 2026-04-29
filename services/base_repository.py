from sqlalchemy.ext.asyncio import AsyncSession

class BaseRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def delete(self, obj):
        await self.db.delete(obj)
        await self.db.commit()

    async def add(self, obj):
        self.db.add(obj)
        await self.db.commit()
        await self.db.refresh(obj)

    async def commit_refresh(self, obj):
        await self.db.commit()
        await self.db.refresh(obj)
