from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.config import get_settings

settings = get_settings()

client: AsyncIOMotorClient = None
db: AsyncIOMotorDatabase = None


async def connect_to_mongo():
    global client, db
    client = AsyncIOMotorClient(settings.mongodb_url)
    db = client[settings.database_name]
    
    # Create indexes for performance
    await db.emails.create_index("timestamp", background=True)
    await db.emails.create_index("folder", background=True)
    await db.emails.create_index("labels", background=True)
    await db.emails.create_index("is_starred", background=True)
    await db.emails.create_index("thread_id", background=True)
    await db.emails.create_index([("folder", 1), ("timestamp", -1)], background=True)
    await db.emails.create_index([("labels", 1), ("timestamp", -1)], background=True)
    
    print(f"✅ Connected to MongoDB: {settings.database_name} with indexes")


async def close_mongo_connection():
    global client
    if client:
        client.close()
        print("🔌 MongoDB connection closed")


def get_database() -> AsyncIOMotorDatabase:
    return db
