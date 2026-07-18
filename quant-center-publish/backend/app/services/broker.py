from typing import Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.models.broker import BrokerCredential
from app.schemas.broker import BrokerCredentialCreate, BrokerCredentialUpdate

logger = structlog.get_logger()


class BrokerService:
    """
    Business service layer managing the orchestration and persistence of generic 
    broker workspace credentials. 

    Insulated entirely from downstream vendor-specific SDK execution mappings.
    """

    @staticmethod
    async def get_by_id(db: AsyncSession, credential_id: int, user_id: int) -> BrokerCredential | None:
        """Fetch a specific broker configuration boundary verified against the owning user."""
        result = await db.execute(
            select(BrokerCredential).where(
                BrokerCredential.id == credential_id,
                BrokerCredential.user_id == user_id
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_multi_by_user(db: AsyncSession, user_id: int) -> Sequence[BrokerCredential]:
        """Retrieve all registered broker connectivity footprints configured for a specific user workspace."""
        result = await db.execute(
            select(BrokerCredential).where(BrokerCredential.user_id == user_id)
        )
        return result.scalars().all()

    @staticmethod
    async def create(db: AsyncSession, user_id: int, obj_in: BrokerCredentialCreate) -> BrokerCredential:
        """Registers an abstract broker venue structure."""
        db_obj = BrokerCredential(
            user_id=user_id,
            broker_name=obj_in.broker_name.lower().strip(),
            client_id=obj_in.client_id.strip(),
            display_name=obj_in.display_name.strip() if obj_in.display_name else None,
            environment=obj_in.environment,
            encrypted_api_key=obj_in.api_key, 
            encrypted_api_secret=obj_in.api_secret,
            encrypted_extra_params=obj_in.extra_params
        )

        try:
            db.add(db_obj)
            await db.commit()
            await db.refresh(db_obj)
        except Exception as err:
            await db.rollback()
            await logger.aerror(
                "Failed database transaction during broker registration sequence", 
                user_id=user_id, 
                broker=obj_in.broker_name,
                error=str(err)
            )
            raise

        await logger.ainfo(
            "Successfully configured new connection profile for execution venue",
            user_id=user_id,
            credential_id=db_obj.id,
            broker=db_obj.broker_name
        )
        return db_obj

    @staticmethod
    async def update(
        db: AsyncSession, 
        db_obj: BrokerCredential, 
        obj_in: BrokerCredentialUpdate
    ) -> BrokerCredential:
        """Performs isolated property mutations across an established broker credential tracking record."""
        update_data = obj_in.model_dump(exclude_unset=True)
        
        if "api_key" in update_data:
            db_obj.encrypted_api_key = update_data.pop("api_key")
        if "api_secret" in update_data:
            db_obj.encrypted_api_secret = update_data.pop("api_secret")
        if "extra_params" in update_data:
            db_obj.encrypted_extra_params = update_data.pop("extra_params")
        if "broker_name" in update_data:
            update_data["broker_name"] = update_data["broker_name"].lower().strip()
        if "client_id" in update_data:
            update_data["client_id"] = update_data["client_id"].strip()

        for field, value in update_data.items():
            setattr(db_obj, field, value)

        try:
            db.add(db_obj)
            await db.commit()
            await db.refresh(db_obj)
        except Exception as err:
            await db.rollback()
            await logger.aerror(
                "Failed database transaction during broker profile state modification", 
                credential_id=db_obj.id,
                error=str(err)
            )
            raise

        await logger.ainfo("Broker connection profile updated dynamically", credential_id=db_obj.id)
        return db_obj

    @staticmethod
    async def delete(db: AsyncSession, credential_id: int, user_id: int) -> bool:
        """
        Soft deletes a target broker configuration by disabling its execution flag state.
        Preserves historical audit trails and protects compliance history from permanent data loss.
        """
        db_obj = await BrokerService.get_by_id(db, credential_id=credential_id, user_id=user_id)
        if not db_obj:
            return False

        # Invert visibility state rather than issuing a raw DELETE SQL statement
        db_obj.is_active = False

        try:
            db.add(db_obj)
            await db.commit()
        except Exception as err:
            await db.rollback()
            await logger.aerror(
                "Failed database transaction during broker entity soft-delete sequence", 
                credential_id=credential_id,
                error=str(err)
            )
            raise

        await logger.ainfo(
            "Broker connection profile deactivated (soft-deleted) successfully", 
            credential_id=credential_id
        )
        return True