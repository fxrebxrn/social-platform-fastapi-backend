from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from typing import Optional, Any

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

    async def add_unique_objects(self, objects: list[Any], detail: str, refresh_obj: Optional[Any] = None):
        try:
            for obj in objects:
                self.db.add(obj)

            await self.db.commit()

            if refresh_obj is not None:
                await self.db.refresh(refresh_obj)

            return refresh_obj

        except IntegrityError:
            await self.db.rollback()
            raise HTTPException(status_code=409, detail=detail)
