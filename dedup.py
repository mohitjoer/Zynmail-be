import asyncio
from app.database import connect_to_mongo, get_database, close_mongo_connection

async def main():
    await connect_to_mongo()
    db = get_database()

    print("Finding duplicates...")
    pipeline = [
        {"$group": {"_id": "$gmail_id", "ids": {"$push": "$_id"}, "count": {"$sum": 1}}},
        {"$match": {"count": {"$gt": 1}}}
    ]
    dupes = await db.emails.aggregate(pipeline).to_list(None)
    print(f"Found {len(dupes)} gmail_ids with duplicates")

    removed = 0
    for dupe in dupes:
        to_delete = dupe["ids"][1:]  # keep first, delete rest
        result = await db.emails.delete_many({"_id": {"$in": to_delete}})
        removed += result.deleted_count

    print(f"Removed {removed} duplicate emails")

    # Create unique index to prevent future duplicates
    try:
        await db.emails.create_index("gmail_id", unique=True, sparse=True)
        print("✅ Created unique index on gmail_id")
    except Exception as e:
        print(f"Index already exists or error: {e}")

    total = await db.emails.count_documents({})
    print(f"Total emails now: {total}")

    await close_mongo_connection()

if __name__ == "__main__":
    asyncio.run(main())
