import os
import json
from fastapi import APIRouter

router = APIRouter(prefix="/api/user", tags=["user"])


# Mock current user — will be replaced with auth later
CURRENT_USER = {
    "id": "user_001",
    "name": "Mohit",
    "email": "mohit@zynmail.com",
    "avatar_url": "",
    "signature": "Sent from Zynmail",
}


@router.get("/me")
async def get_current_user():
    """Get the current user's profile."""
    if os.path.exists("user_profile.json"):
        with open("user_profile.json", "r") as f:
            data = json.load(f)
            return {
                "id": data.get("id", "user_001"),
                "name": data.get("name", "User"),
                "email": data.get("email", ""),
                "avatar_url": data.get("picture", ""),
                "signature": "Sent from Zynmail",
            }
    return CURRENT_USER
