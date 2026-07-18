from typing import Literal

from pydantic import BaseModel, Field

Theme = Literal["dark", "light"]


class UserSettings(BaseModel):
    theme: Theme = Field(default="dark")
    notificationsEnabled: bool = Field(default=True)
