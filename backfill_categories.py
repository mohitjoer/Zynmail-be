import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from app.config import get_settings
from app.services.ai_classifier import classify_email

async def main():
    settings = get_settings()
    client = AsyncIOMotorClient(settings.mongodb_url)
    db = client["zynmail"]
    
    # Get inbox emails without a category
    cursor = db.emails.find({"folder": "inbox", "ai_category": {"$in": [None, ""]}}).sort("timestamp", -1).limit(50)
    emails = await cursor.to_list(length=50)
    
    print(f"Found {len(emails)} emails to categorize.")
    
    for email in emails:
        sender = email.get("from", {}).get("name", "")
        subject = email.get("subject", "")
        snippet = email.get("snippet", "")
        
        category = classify_email(sender, subject, snippet)
        
        if category:
            await db.emails.update_one(
                {"_id": email["_id"]},
                {"$set": {"ai_category": category}}
            )
            print(f"Categorized: '{subject}' -> {category}")
        else:
            print(f"No category for: '{subject}'")
            
if __name__ == "__main__":
    asyncio.run(main())
