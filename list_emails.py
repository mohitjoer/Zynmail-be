import os
import json
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
        
    service = build('gmail', 'v1', credentials=creds)
    results = service.users().messages().list(userId='me', maxResults=50).execute()
    print("API Response:", results)

if __name__ == "__main__":
    main()
