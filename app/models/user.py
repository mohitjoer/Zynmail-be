from pydantic import BaseModel
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
    avatar_url: str
    signature: str
