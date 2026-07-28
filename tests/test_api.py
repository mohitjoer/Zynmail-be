import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database import connect_to_mongo, close_mongo_connection, get_database
from app.seed.seed_data import seed_database
from app.config import get_settings

@pytest.fixture(autouse=True)
async def setup_db():
    await connect_to_mongo()
    db = get_database()
    await seed_database(db)
    yield
    await close_mongo_connection()

@pytest.fixture
async def async_client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client

@pytest.mark.asyncio
async def test_health_check(async_client):
    response = await async_client.get("/api/health")
    assert response.status_code == 200
    settings = get_settings()
    assert response.json() == {"status": "healthy", "app": settings.app_name}

@pytest.mark.asyncio
async def test_get_emails_empty(async_client):
    response = await async_client.get("/api/emails")
    assert response.status_code == 200
    data = response.json()
    assert "emails" in data
    assert isinstance(data["emails"], list)

@pytest.mark.asyncio
async def test_get_user_profile(async_client):
    response = await async_client.get("/api/user/me")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Mohit"
    assert data["email"] == "mohit@zynmail.com"
