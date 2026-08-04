import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from app.config import get_settings
from app.services.ai_classifier import classify_email

async def main():
    settings = get_settings()
    client = AsyncIOMotorClient(settings.mongodb_url)
    db = client["zynmail"]
    
    # Get all inbox emails to re-classify with the new rules
    cursor = db.emails.find({"folder": "inbox"}).sort("timestamp", -1)
    emails = await cursor.to_list(length=500)
    
    print(f"Found {len(emails)} emails to categorize.")
    
    updated_count = 0
    for email in emails:
        sender = f"{email.get('from', {}).get('name', '')} {email.get('from', {}).get('email', '')}"
        subject = email.get("subject", "")
        snippet = email.get("snippet", "")
        
        category = classify_email(sender, subject, snippet)
        
        if category:
            await db.emails.update_one(
                {"_id": email["_id"]},
                {"$set": {"ai_category": category}}
            )
            updated_count += 1
            print(f"[{category}] '{subject}' from {sender}")
            
    print(f"Successfully re-categorized {updated_count} emails.")
            
if __name__ == "__main__":
    asyncio.run(main())
