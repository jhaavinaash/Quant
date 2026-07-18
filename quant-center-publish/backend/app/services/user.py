from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.models.user import User
from app.schemas.user import UserCreate
from app.core.security import get_password_hash, verify_password

logger = structlog.get_logger()


class UserService:
    """
    Business service layer orchestrating user entity persistence, cryptographically secure 
    password hashing wrappers, and identity validation workflows.
    """

    @staticmethod
    async def get_by_email(db: AsyncSession, email: str) -> User | None:
        """Query an active database session for a specific User matching the unique email coordinate."""
        result = await db.execute(select(User).where(User.email == email.lower().strip()))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_username(db: AsyncSession, username: str) -> User | None:
        """Query an active database session for a specific User matching the unique username coordinate."""
        result = await db.execute(select(User).where(User.username == username.strip()))
        return result.scalar_one_or_none()

    @staticmethod
    async def create(db: AsyncSession, obj_in: UserCreate) -> User:
        """
        Validates uniqueness constraints and provisions a brand new platform operator
        with a safely salted, non-reversible cryptographic password hash sequence.
        """
        # Commit a secure password computation cycle out-of-band before initialization
        hashed_pwd = get_password_hash(obj_in.password)
        
        db_user = User(
            email=obj_in.email.lower().strip(),
            username=obj_in.username.strip(),
            hashed_password=hashed_pwd,
            is_active=True
        )
        
        try:
            db.add(db_user)
            await db.commit()
            await db.refresh(db_user)
        except Exception as err:
            # Transaction safeguard: Roll back to prevent session corruption on failure
            await db.rollback()
            await logger.aerror("Failed database write transaction during user creation sequence", error=str(err))
            raise
        
        await logger.ainfo("Successfully provisioned new system operator account", user_id=db_user.id, username=db_user.username)
        return db_user

    @staticmethod
    async def authenticate(db: AsyncSession, identity: str, password: str) -> User | None:
        """
        Verifies login credentials by evaluating an identification handle (email or username) 
        and validating the corresponding raw string against the saved secret hash matrix.
        """
        if "@" in identity:
            user = await UserService.get_by_email(db, identity)
        else:
            user = await UserService.get_by_username(db, identity)
            
        if not user or not user.is_active:
            return None
            
        if not verify_password(password, user.hashed_password):
            return None
            
        return user