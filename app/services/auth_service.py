import re
import os
import json
import uuid
from datetime import datetime, timezone
import bcrypt
from fastapi import HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.models.user import UserResponse

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


def validate_email_format(email: str) -> str:
    """Validates and normalizes email string."""
    clean_email = email.strip().lower()
    if not clean_email or not EMAIL_REGEX.match(clean_email):
        raise HTTPException(status_code=400, detail="Please enter a valid email address.")
    return clean_email


def hash_password(password: str) -> str:
    """Securely hashes a plaintext password using bcrypt with automatic salt."""
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters long.")
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plaintext password against a stored bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def derive_name_from_email(email: str) -> str:
    """Generates a pleasant display name from an email username."""
    username = email.split("@")[0]
    # Replace dots, underscores, hyphens with spaces and capitalize
    name_parts = re.sub(r"[._-]+", " ", username).strip().split()
    if name_parts:
        return " ".join(part.capitalize() for part in name_parts)
    return "Zynmail User"


async def register_user(db: AsyncIOMotorDatabase, email: str, password: str) -> dict:
    """Registers a new user with email and password in MongoDB."""
    clean_email = validate_email_format(email)
    
    # Check if user already exists
    existing = await db.users.find_one({"email": clean_email})
    if existing:
        raise HTTPException(status_code=400, detail="An account with this email already exists. Please sign in.")

    hashed_pw = hash_password(password)
    user_id = f"usr_{uuid.uuid4().hex[:12]}"
    display_name = derive_name_from_email(clean_email)
    
    # Generate avatar using Dicebear initials / bottts
    avatar_url = f"https://api.dicebear.com/7.x/initials/svg?seed={display_name}&backgroundColor=3b82f6,8b5cf6,ec4899"

    user_doc = {
        "id": user_id,
        "email": clean_email,
        "password_hash": hashed_pw,
        "name": display_name,
        "avatar_url": avatar_url,
        "signature": "Sent from Zynmail — Email that thinks before you do.",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.users.insert_one(user_doc)

    # Write profile cache for seamless local state
    save_session_profile({
        "id": user_id,
        "name": display_name,
        "email": clean_email,
        "picture": avatar_url,
        "signature": user_doc["signature"]
    })

    return {
        "id": user_id,
        "name": display_name,
        "email": clean_email,
        "avatar_url": avatar_url,
        "signature": user_doc["signature"]
    }


async def authenticate_user(db: AsyncIOMotorDatabase, email: str, password: str) -> dict:
    """Authenticates a user with email and password against MongoDB."""
    clean_email = validate_email_format(email)
    
    user = await db.users.find_one({"email": clean_email})
    if not user or "password_hash" not in user:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    if not verify_password(password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    user_id = user.get("id") or str(user.get("_id"))
    display_name = user.get("name") or derive_name_from_email(clean_email)
    avatar_url = user.get("avatar_url") or f"https://api.dicebear.com/7.x/initials/svg?seed={display_name}"
    signature = user.get("signature") or "Sent from Zynmail"

    # Save session profile
    save_session_profile({
        "id": user_id,
        "name": display_name,
        "email": clean_email,
        "picture": avatar_url,
        "signature": signature
    })

    return {
        "id": user_id,
        "name": display_name,
        "email": clean_email,
        "avatar_url": avatar_url,
        "signature": signature
    }


from app.services.encryption_service import save_encrypted_json_file, load_encrypted_json_file

def save_session_profile(profile_data: dict):
    """Persists user profile to user_profile.json with AES-256 encryption."""
    save_encrypted_json_file("user_profile.json", profile_data)


def load_session_profile() -> dict | None:
    """Loads and decrypts user profile from user_profile.json."""
    return load_encrypted_json_file("user_profile.json")
