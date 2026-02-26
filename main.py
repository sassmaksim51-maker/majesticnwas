from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv

load_dotenv()

from database import create_tables
from routers import users, posts, likes, comments, favorites
from telegram_bot import router as telegram_router
from models import User
from database import AsyncSessionLocal
from auth import get_password_hash
from sqlalchemy import select


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup
    await create_tables()
    # Create admin user if not exists
    await create_admin()
    yield


async def create_admin():
    admin_username = os.getenv("ADMIN_USERNAME", "admin")
    admin_password = os.getenv("ADMIN_PASSWORD", "admin123")
    admin_email = os.getenv("ADMIN_EMAIL", "admin@example.com")

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.username == admin_username))
        if not result.scalar_one_or_none():
            admin = User(
                username=admin_username,
                email=admin_email,
                password_hash=get_password_hash(admin_password),
                is_admin=True
            )
            db.add(admin)
            await db.commit()
            print(f"Admin user created: {admin_username}")


app = FastAPI(title="News Site API", lifespan=lifespan)

# CORS - allow frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change to your frontend URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(users.router)
app.include_router(posts.router)
app.include_router(likes.router)
app.include_router(comments.router)
app.include_router(favorites.router)
app.include_router(telegram_router)


@app.get("/")
async def root():
    return {"status": "ok", "message": "News Site API"}


@app.get("/api/setup-webhook")
async def setup_webhook(base_url: str):
    """Setup Telegram webhook. Call once after deployment."""
    from telegram_bot import set_webhook
    return await set_webhook(base_url)
