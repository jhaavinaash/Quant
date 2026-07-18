from sqlalchemy import select
from typing import AsyncGenerator
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import JWT_ALGORITHM
from app.schemas.token import TokenData
from app.models.user import User  # Ensure this matches your project structure

logger = structlog.get_logger()

# Establish the standard OAuth2 token interception scheme
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_PREFIX}/auth/login"
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency provider yielding scoped asynchronous transactional database sessions."""
    async with SessionLocal() as session:
        try:
            yield session
        except Exception as err:
            await logger.aerror("Database dependency context failure", error=str(err))
            raise

async def get_current_token_data(token: str = Depends(oauth2_scheme)) -> TokenData:
    """Core security dependency that intercepts, extracts, and decodes incoming JWT claims."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate authorization credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(
            token, 
            settings.SECRET_KEY, 
            algorithms=[JWT_ALGORITHM]
        )
        user_id: str | None = payload.get("sub")
        username: str | None = payload.get("username")
        
        if user_id is None:
            raise credentials_exception
            
        return TokenData(user_id=user_id, username=username)
        
    except JWTError as err:
        await logger.awarn("Invalid or expired token", error=str(err))
        raise credentials_exception

async def get_current_user(
    db: AsyncSession = Depends(get_db), 
    token_data: TokenData = Depends(get_current_token_data)
) -> User:
    """Retrieves the current authenticated user from the database."""
    # Assuming you have a way to fetch the user by ID
    # Update this lookup based on your specific User model implementation
    result = await db.execute(select(User).where(User.id == int(token_data.user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

async def get_current_superuser(current_user: User = Depends(get_current_user)) -> User:
    """Dependency to verify if the current user has superuser privileges."""
    if not getattr(current_user, "is_superuser", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="The user does not have enough privileges"
        )
    return current_user