from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from src.config import settings

_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(api_key: str | None = Security(_header)) -> None:
    if not api_key or api_key != settings.backend_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-API-Key header",
        )
