import os
import json
from fastapi import APIRouter
from pydantic import BaseModel

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
                "signature": data.get("signature", "Sent from Zynmail"),
            }
    return CURRENT_USER

class UserUpdate(BaseModel):
    name: str | None = None
    signature: str | None = None

@router.put("/me")
async def update_current_user(update_data: UserUpdate):
    data = CURRENT_USER.copy()
    if os.path.exists("user_profile.json"):
        with open("user_profile.json", "r") as f:
            try:
                data = json.load(f)
            except:
                pass
    
    if update_data.name:
        data["name"] = update_data.name
    if update_data.signature is not None:
        data["signature"] = update_data.signature
        
    with open("user_profile.json", "w") as f:
        json.dump(data, f)
        
    return {"status": "success", "message": "Profile updated"}
