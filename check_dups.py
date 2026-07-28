import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def main():
    client = AsyncIOMotorClient('mongodb+srv://Vercel-Admin-atlas-citron-school:cNphrvKaTdiDGY1B@atlas-citron-school.9qebpci.mongodb.net/?retryWrites=true&w=majority')
    db = client.zynmail
    
    pipeline = [
        {"$group": {"_id": "$gmail_id", "count": {"$sum": 1}}},
        {"$match": {"count": {"$gt": 1}}}
    ]
    
    dups = await db.emails.aggregate(pipeline).to_list(None)
    if not dups:
        print("No duplicates found.")
    else:
        print(f"Found {len(dups)} duplicate gmail_ids!")
        print(dups)

asyncio.run(main())
