from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.api.deps import get_db
from app.services.user import UserService
from app.schemas.user import UserCreate, UserResponse
from app.schemas.token import Token
from app.core.security import create_access_token
from app.core.config import settings

logger = structlog.get_logger()

# Leave the router definition prefix clean; centralized prefixing is managed inside api.py
router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_in: UserCreate, 
    db: AsyncSession = Depends(get_db)
):
    """
    Exposes a registration entryway to provision a new trading desk operator.
    Validates email and username conflicts before committing transactional writes.
    """
    existing_email = await UserService.get_by_email(db, user_in.email)
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account matching this email registration already exists."
        )
        
    existing_username = await UserService.get_by_username(db, user_in.username)
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This system handle identity is already claimed."
        )
        
    new_user = await UserService.create(db, obj_in=user_in)
    return new_user


@router.post("/login", response_model=Token)
async def login_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """
    OAuth2 compatible token login endpoint. Evaluates standardized OAuth2 form elements,
    cross-references identity parameters, and outputs a signed JWT string.
    """
    user = await UserService.authenticate(
        db, 
        identity=form_data.username, 
        password=form_data.password
    )
    
    if not user:
        await logger.awarn("Failed authentication attempt rejected", identity=form_data.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect identification handle or matching password sequence.",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    # Safeguard: Explicitly intercept verified users who have been administratively disabled
    if not user.is_active:
        await logger.awarn("Authentication blocked for disabled operator account", user_id=user.id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive."
        )
        
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    access_token = create_access_token(
        subject=user.id,
        expires_delta=access_token_expires
    )   
    
    return Token(access_token=access_token, token_type="bearer")