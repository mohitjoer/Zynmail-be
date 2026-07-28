from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import get_settings
from app.database import connect_to_mongo, close_mongo_connection, get_database
from app.routes.emails import router as emails_router
from app.routes.users import router as users_router
from app.seed.seed_data import seed_database

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_to_mongo()
    db = get_database()
    # await seed_database(db)
    yield
    # Shutdown
    await close_mongo_connection()


app = FastAPI(
    title=settings.app_name,
    description="AI-powered mailing platform — API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.routes.auth import router as auth_router
from app.routes.chat import router as chat_router

# Routes
app.include_router(emails_router)
app.include_router(users_router)
app.include_router(auth_router)
app.include_router(chat_router)


@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "app": settings.app_name}
