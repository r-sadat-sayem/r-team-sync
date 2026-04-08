from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import OAuthConnection


async def get_oauth_connection(
    db: AsyncSession,
    user_id: int,
    provider: str,
) -> Optional[OAuthConnection]:
    result = await db.execute(
        select(OAuthConnection).where(
            OAuthConnection.user_id == user_id,
            OAuthConnection.provider == provider,
        )
    )
    return result.scalar_one_or_none()


async def upsert_oauth_connection(
    db: AsyncSession,
    user_id: int,
    provider: str,
    **fields: str,
) -> OAuthConnection:
    record = await get_oauth_connection(db, user_id, provider)
    if not record:
        record = OAuthConnection(user_id=user_id, provider=provider)
        db.add(record)

    for key, value in fields.items():
        setattr(record, key, value)

    await db.commit()
    await db.refresh(record)
    return record


async def delete_oauth_connection(
    db: AsyncSession,
    user_id: int,
    provider: str,
) -> None:
    record = await get_oauth_connection(db, user_id, provider)
    if record:
        await db.delete(record)
        await db.commit()
