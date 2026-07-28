import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

async def main():
    client = AsyncIOMotorClient('mongodb+srv://Vercel-Admin-atlas-citron-school:cNphrvKaTdiDGY1B@atlas-citron-school.9qebpci.mongodb.net/?retryWrites=true&w=majority')
    db = client.zynmail
    
    doc = await db.emails.find_one({"_id": ObjectId("6a650a47468e71a21e9079ea")})
    if doc:
        print(f"Folder: {doc.get('folder')}")
        print(f"Pending: {doc.get('pending_gmail_sync')}")
    else:
        print("Not found")

asyncio.run(main())
