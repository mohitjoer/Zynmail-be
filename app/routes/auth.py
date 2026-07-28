from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os
import json
from google_auth_oauthlib.flow import Flow

router = APIRouter(prefix="/api/auth", tags=["auth"])

SCOPES = [
    'https://mail.google.com/',
    'https://www.googleapis.com/auth/userinfo.profile',
    'https://www.googleapis.com/auth/userinfo.email',
    'openid'
]

class CodeExchangeRequest(BaseModel):
    code: str

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
        
        with open('user_credentials.json', 'w') as f:
            f.write(creds.to_json())
        os.chmod('user_credentials.json', 0o600)
            
        # Fetch user profile
        user_info_resp = requests.get(
            'https://www.googleapis.com/oauth2/v2/userinfo',
            headers={'Authorization': f'Bearer {token_data.get("access_token")}'}
        )
        if user_info_resp.ok:
            user_info = user_info_resp.json()
            with open('user_profile.json', 'w') as f:
                json.dump(user_info, f)

            
        return {"status": "success", "message": "Successfully connected to Gmail!"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/status")
async def auth_status():
    return {"connected": os.path.exists("user_credentials.json")}
