import asyncio
from app.database import connect_to_mongo, get_database, close_mongo_connection
from app.services.gmail_service import sync_gmail_emails

async def main():
    await connect_to_mongo()
    db = get_database()
    print("Clearing old data...")
    await db.emails.delete_many({})
    print("Syncing ALL emails from Gmail...")
    res = await sync_gmail_emails(db, max_results=500)
    print("Result:", res)
    total = await db.emails.count_documents({})
    print(f"Total emails in DB: {total}")
    
    # Ensure unique index exists
    try:
        await db.emails.create_index("gmail_id", unique=True, sparse=True)
        print("✅ Unique index on gmail_id confirmed")
    except Exception:
        pass
    
    await close_mongo_connection()

if __name__ == "__main__":
    asyncio.run(main())
