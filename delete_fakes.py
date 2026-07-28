import asyncio
from app.database import connect_to_mongo, get_database, close_mongo_connection

async def main():
    await connect_to_mongo()
    db = get_database()
    result = await db.emails.delete_many({"gmail_id": {"$exists": False}})
    print(f"Deleted {result.deleted_count} fake emails.")
    await close_mongo_connection()

if __name__ == "__main__":
    asyncio.run(main())
