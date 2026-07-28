import asyncio
from app.database import connect_to_mongo, get_database, close_mongo_connection

async def main():
    await connect_to_mongo()
    db = get_database()
    
    # Add "SENT" label to any email with folder="sent" that doesn't have it
    result = await db.emails.update_many(
        {"folder": "sent", "labels": {"$ne": "SENT"}},
        {"$addToSet": {"labels": "SENT"}}
    )
    print(f"Fixed {result.modified_count} sent emails.")
    
    await close_mongo_connection()

if __name__ == "__main__":
    asyncio.run(main())
