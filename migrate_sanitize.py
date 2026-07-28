import asyncio
from app.database import connect_to_mongo, get_database, close_mongo_connection
from app.services.sanitizer import sanitize_email_html

async def main():
    await connect_to_mongo()
    db = get_database()
    
    print("Sanitizing all existing emails in the database...")
    emails_cursor = db.emails.find({})
    
    count = 0
    async for email in emails_cursor:
        body_html = email.get("body_html")
        if body_html:
            sanitized = sanitize_email_html(body_html)
            await db.emails.update_one(
                {"_id": email["_id"]},
                {"$set": {"body_html": sanitized}}
            )
            count += 1
            if count % 10 == 0:
                print(f"Sanitized {count} emails...")
                
    print(f"Done! Sanitized a total of {count} emails.")
    await close_mongo_connection()

if __name__ == "__main__":
    asyncio.run(main())
