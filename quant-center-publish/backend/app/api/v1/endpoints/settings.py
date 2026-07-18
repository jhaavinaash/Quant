from fastapi import APIRouter, Depends, status

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.settings import UserSettings
from app.services.settings_service import SettingsService

router = APIRouter()


@router.get("", response_model=UserSettings, status_code=status.HTTP_200_OK)
async def get_settings(current_user: User = Depends(get_current_user)):
    """
    Returns UI preferences for the authenticated user.
    """
    return SettingsService.get_for_user(current_user.id)


@router.put("", status_code=status.HTTP_204_NO_CONTENT)
async def update_settings(
    settings_in: UserSettings,
    current_user: User = Depends(get_current_user),
):
    """
    Persists UI preferences for the authenticated user.
    """
    SettingsService.update_for_user(current_user.id, settings_in)
