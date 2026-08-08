import os
import json
from fastapi import APIRouter
from pydantic import BaseModel
from app.services.encryption_service import load_encrypted_json_file, save_encrypted_json_file

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
        try:
            data = load_encrypted_json_file("user_profile.json")
            if data and isinstance(data, dict):
                return {
                    "id": data.get("id", "user_001"),
                    "name": data.get("name", "User"),
                    "email": data.get("email", ""),
                    "avatar_url": data.get("picture", ""),
                    "signature": data.get("signature", "Sent from Zynmail"),
                }
        except Exception as e:
            print(f"Error loading user profile: {e}")
    return CURRENT_USER


class UserUpdate(BaseModel):
    name: str | None = None
    signature: str | None = None


@router.put("/me")
async def update_current_user(update_data: UserUpdate):
    data = CURRENT_USER.copy()
    if os.path.exists("user_profile.json"):
        try:
            loaded = load_encrypted_json_file("user_profile.json")
            if loaded and isinstance(loaded, dict):
                data = loaded
        except Exception as e:
            print(f"Error reading profile for update: {e}")
    
    if update_data.name:
        data["name"] = update_data.name
    if update_data.signature is not None:
        data["signature"] = update_data.signature
        
    save_encrypted_json_file("user_profile.json", data)
        
    return {"status": "success", "message": "Profile updated"}
