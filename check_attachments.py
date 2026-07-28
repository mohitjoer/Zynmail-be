from app.database import get_database, connect_to_mongo, close_mongo_connection
import asyncio

async def main():
    await connect_to_mongo()
    db = get_database()
    emails = await db.emails.find({"has_attachments": True}).to_list(length=10)
    for e in emails:
        print(e.get("subject"), e.get("attachments"))
    await close_mongo_connection()

if __name__ == "__main__":
    asyncio.run(main())
