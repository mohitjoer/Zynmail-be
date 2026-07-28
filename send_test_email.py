import os
import json
import base64
from email.message import EmailMessage
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

CREDENTIALS_FILE = 'user_credentials.json'

def main():
    if not os.path.exists(CREDENTIALS_FILE):
        print("No credentials found.")
        return
        
    with open(CREDENTIALS_FILE, 'r') as f:
        creds_data = json.load(f)
        creds = Credentials.from_authorized_user_info(creds_data)
        
    # We need gmail.send scope. Does the user have it?
    # Our SCOPES only included: 'https://www.googleapis.com/auth/gmail.readonly'
    print("Scopes:", creds.scopes)

if __name__ == "__main__":
    main()
