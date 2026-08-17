import os
import json
from fastapi import APIRouter
from pydantic import BaseModel
from app.services.encryption_service import load_encrypted_json_file, save_encrypted_json_file

router = APIRouter(prefix="/api/user", tags=["user"])


from app.database import get_database
from motor.motor_asyncio import AsyncIOMotorDatabase
from fastapi import Depends

@router.get("/me")
async def get_current_user(db: AsyncIOMotorDatabase = Depends(get_database)):
    """Get the current user's profile."""
    # Check encrypted user_profile.json first (Gmail OAuth profile)
    if os.path.exists("user_profile.json"):
        try:
            data = load_encrypted_json_file("user_profile.json")
            if data and isinstance(data, dict) and data.get("email"):
                return {
                    "id": str(data.get("id", "user_001")),
                    "name": data.get("name", data.get("email", "").split("@")[0]),
                    "email": data.get("email", ""),
                    "avatar_url": data.get("picture", ""),
                    "signature": data.get("signature", "Sent from Zynmail"),
                }
        except Exception as e:
            print(f"Error loading user profile: {e}")

    # Fallback to Better Auth user collection in MongoDB
    try:
        latest_user = await db["user"].find_one({}, sort=[("createdAt", -1)])
        if latest_user:
            return {
                "id": str(latest_user.get("_id", "user_001")),
                "name": latest_user.get("name", latest_user.get("email", "").split("@")[0]),
                "email": latest_user.get("email", ""),
                "avatar_url": latest_user.get("image", ""),
                "signature": latest_user.get("signature", "Sent from Zynmail"),
            }
    except Exception as e:
        print(f"Error querying user from DB: {e}")

    return {
        "id": "user_001",
        "name": "User",
        "email": "",
        "avatar_url": "",
        "signature": "Sent from Zynmail",
    }


class UserUpdate(BaseModel):
    name: str | None = None
    signature: str | None = None


@router.put("/me")
async def update_current_user(update_data: UserUpdate, db: AsyncIOMotorDatabase = Depends(get_database)):
    data = {
        "id": "user_001",
        "name": "User",
        "email": "",
        "signature": "Sent from Zynmail"
    }
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
    
    # Also update MongoDB user document if present
    try:
        update_fields = {}
        if update_data.name:
            update_fields["name"] = update_data.name
        if update_data.signature is not None:
            update_fields["signature"] = update_data.signature
        if update_fields:
            await db["user"].update_many({}, {"$set": update_fields})
    except Exception as e:
        print(f"Error syncing profile update to DB: {e}")
        
    return {"status": "success", "message": "Profile updated"}
