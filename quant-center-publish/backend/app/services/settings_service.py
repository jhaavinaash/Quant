from app.schemas.settings import UserSettings

_DEFAULT_SETTINGS = UserSettings()


class SettingsService:
    _store: dict[int, UserSettings] = {}

    @classmethod
    def get_for_user(cls, user_id: int) -> UserSettings:
        return cls._store.get(user_id, _DEFAULT_SETTINGS.model_copy())

    @classmethod
    def update_for_user(cls, user_id: int, settings: UserSettings) -> UserSettings:
        cls._store[user_id] = settings
        return settings
