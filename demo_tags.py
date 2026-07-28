import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from app.config import get_settings

async def main():
    settings = get_settings()
    client = AsyncIOMotorClient(settings.mongodb_url)
    db = client["zynmail"]
    
    # Fetch top 10 inbox emails
    cursor = db.emails.find({"folder": "inbox"}).sort("timestamp", -1).limit(10)
    emails = await cursor.to_list(length=10)
    
    if len(emails) >= 4:
        # Manually set the first few to different categories for UI testing
        await db.emails.update_one({"_id": emails[0]["_id"]}, {"$set": {"ai_category": "Needs Reply"}})
        await db.emails.update_one({"_id": emails[1]["_id"]}, {"$set": {"ai_category": "VIP"}})
        await db.emails.update_one({"_id": emails[2]["_id"]}, {"$set": {"ai_category": "Linear"}})
        await db.emails.update_one({"_id": emails[3]["_id"]}, {"$set": {"ai_category": "Noise"}})
        await db.emails.update_one({"_id": emails[4]["_id"]}, {"$set": {"ai_category": "VIP"}})
        
    print("Updated top emails with demo categories!")
    
if __name__ == "__main__":
    asyncio.run(main())
