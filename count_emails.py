import asyncio
from app.database import connect_to_mongo, get_database, close_mongo_connection

async def main():
    await connect_to_mongo()
    db = get_database()
    count = await db.emails.count_documents({"gmail_id": {"$exists": True}})
    print(f"Total synced emails in DB: {count}")
    await close_mongo_connection()

if __name__ == "__main__":
    asyncio.run(main())
