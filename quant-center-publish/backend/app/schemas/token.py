from pydantic import BaseModel, ConfigDict


class Token(BaseModel):
    """Schema defining the structure of a successful authentication token payload response."""
    access_token: str
    token_type: str = "bearer"
    
    model_config = ConfigDict(frozen=True)


class TokenData(BaseModel):
    """
    Schema representing the decoded inside contents of a verified JSON Web Token.
    Used by dependency injection layers to pass authenticated context downstream.
    """
    user_id: str | None = None
    username: str | None = None
    
    model_config = ConfigDict(frozen=True)