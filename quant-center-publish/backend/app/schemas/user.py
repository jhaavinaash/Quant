from pydantic import BaseModel, EmailStr, Field, ConfigDict


class UserBase(BaseModel):
    """Base Pydantic schema enforcing shared attributes across database-bound User instances."""
    email: EmailStr = Field(..., description="Primary contact and notification email sequence")
    username: str = Field(..., min_length=3, max_length=50, description="Unique identity system handle identifier")


class UserCreate(UserBase):
    """Schema validating incoming raw payloads during new registration sequences."""
    password: str = Field(..., min_length=8, max_length=128, description="Plaintext initial registration password string")


class UserLogin(BaseModel):
    """Schema validating inbound JSON bodies for direct verification token exchange requests."""
    username: str = Field(..., description="System identity handle identifier or registration email")
    password: str = Field(..., description="Cryptographic password matching sequence")
    
    model_config = ConfigDict(frozen=True)


class UserResponse(UserBase):
    """Safe system outbound representation schema filtering out sensitive cryptographic variables."""
    id: int
    is_active: bool = True
    
    # Enables Pydantic v2 to natively read lazy-loaded SQLAlchemy ORM model mappings
    model_config = ConfigDict(from_attributes=True)