from pydantic import BaseModel, EmailStr, Field
from typing import Optional


class UserProfile(BaseModel):
    """User profile document schema."""
    id: Optional[str] = None
    name: str
    email: str
    avatar_url: str = ""
    signature: str = ""


class UserResponse(BaseModel):
    """API response for user profile."""
    id: str
    name: str
    email: str
    avatar_url: str = ""
    signature: str = "Sent from Zynmail"


class UserAuthRequest(BaseModel):
    """Sign up and Sign in request containing strictly email and password."""
    email: str = Field(..., description="User email address")
    password: str = Field(..., min_length=6, description="User password (minimum 6 characters)")


class AuthResponse(BaseModel):
    """Standardized authentication response."""
    status: str
    message: str
    user: Optional[UserResponse] = None
    token: Optional[str] = None
