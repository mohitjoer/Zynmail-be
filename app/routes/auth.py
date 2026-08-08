from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import os
import json
from google_auth_oauthlib.flow import Flow
from app.database import get_database
from app.models.user import UserAuthRequest, AuthResponse, UserResponse
from app.services.auth_service import register_user, authenticate_user
from motor.motor_asyncio import AsyncIOMotorDatabase

router = APIRouter(prefix="/api/auth", tags=["auth"])

SCOPES = [
    'https://mail.google.com/',
    'https://www.googleapis.com/auth/userinfo.profile',
    'https://www.googleapis.com/auth/userinfo.email',
    'openid'
]

class CodeExchangeRequest(BaseModel):
    code: str


# ==========================================
# Email & Password Authentication Endpoints
# ==========================================

@router.post("/signup", response_model=AuthResponse)
@router.post("/register", response_model=AuthResponse)
async def signup(req: UserAuthRequest, db: AsyncIOMotorDatabase = Depends(get_database)):
    """Registers a new user with email and password."""
    user = await register_user(db, req.email, req.password)
    return AuthResponse(
        status="success",
        message="Account created successfully!",
        user=UserResponse(**user)
    )


@router.post("/signin", response_model=AuthResponse)
@router.post("/login", response_model=AuthResponse)
async def signin(req: UserAuthRequest, db: AsyncIOMotorDatabase = Depends(get_database)):
    """Authenticates an existing user with email and password."""
    user = await authenticate_user(db, req.email, req.password)
    return AuthResponse(
        status="success",
        message="Signed in successfully!",
        user=UserResponse(**user)
    )


# ==========================================
# Google OAuth Endpoints
# ==========================================

@router.get("/google/url")
async def get_google_auth_url():
    if not os.path.exists("client_secret.json"):
        raise HTTPException(status_code=500, detail="client_secret.json missing")
    
    import urllib.parse
    with open('client_secret.json', 'r') as f:
        client_secret_data = json.load(f)['web']
        
    params = urllib.parse.urlencode({
        'client_id': client_secret_data['client_id'],
        'redirect_uri': 'http://localhost:3000/home',
        'response_type': 'code',
        'scope': ' '.join(SCOPES),
        'access_type': 'offline',
        'prompt': 'consent'
    })
    
    return {"url": f"{client_secret_data['auth_uri']}?{params}"}

@router.post("/google/callback")
async def google_auth_callback(req: CodeExchangeRequest):
    if not os.path.exists("client_secret.json"):
        raise HTTPException(status_code=500, detail="client_secret.json missing")
    
    import requests
    from google.oauth2.credentials import Credentials

    with open('client_secret.json', 'r') as f:
        client_secret_data = json.load(f)['web']
        
    try:
        resp = requests.post('https://oauth2.googleapis.com/token', data={
            'code': req.code,
            'client_id': client_secret_data['client_id'],
            'client_secret': client_secret_data['client_secret'],
            'redirect_uri': 'http://localhost:3000/home',
            'grant_type': 'authorization_code'
        })
        
        if not resp.ok:
            raise Exception(f"Token exchange failed: {resp.text}")
            
        token_data = resp.json()
        
        creds = Credentials(
            token=token_data.get('access_token'),
            refresh_token=token_data.get('refresh_token'),
            token_uri='https://oauth2.googleapis.com/token',
            client_id=client_secret_data['client_id'],
            client_secret=client_secret_data['client_secret']
        )
        
        from app.services.encryption_service import save_encrypted_json_file, load_encrypted_json_file
        save_encrypted_json_file('user_credentials.json', json.loads(creds.to_json()))
            
        # Fetch user profile
        user_info_resp = requests.get(
            'https://www.googleapis.com/oauth2/v2/userinfo',
            headers={'Authorization': f'Bearer {token_data.get("access_token")}'}
        )
        if user_info_resp.ok:
            user_info = user_info_resp.json()
            save_encrypted_json_file('user_profile.json', user_info)
            
        return {"status": "success", "message": "Successfully connected to Gmail!"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/status")
async def auth_status():
    from app.services.encryption_service import load_encrypted_json_file
    has_profile = os.path.exists("user_profile.json")
    has_creds = os.path.exists("user_credentials.json")
    
    gmail_email = None
    gmail_scopes = []
    if has_creds:
        try:
            creds_data = load_encrypted_json_file("user_credentials.json")
            if creds_data:
                gmail_scopes = creds_data.get("scopes", SCOPES)
        except Exception:
            pass
            
    user_info = {}
    if has_profile:
        try:
            profile_data = load_encrypted_json_file("user_profile.json")
            if profile_data:
                user_info = profile_data
                gmail_email = user_info.get("email")
        except Exception:
            pass

    return {
        "authenticated": has_profile or has_creds,
        "connected": has_creds or has_profile,
        "gmail_connected": has_creds,
        "gmail_email": gmail_email,
        "gmail_scopes": gmail_scopes,
        "user": user_info
    }

@router.post("/gmail/disconnect")
@router.post("/gmail/unlink")
async def disconnect_gmail():
    """Unlinks and removes Gmail OAuth credentials while preserving user account."""
    try:
        if os.path.exists("user_credentials.json"):
            os.remove("user_credentials.json")
        return {"status": "success", "message": "Gmail account unlinked successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/logout")
async def logout():
    try:
        if os.path.exists("user_credentials.json"):
            os.remove("user_credentials.json")
        if os.path.exists("user_profile.json"):
            os.remove("user_profile.json")
        return {"status": "success", "message": "Logged out successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
