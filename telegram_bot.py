import os
import httpx
from fastapi import APIRouter, Request, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import AsyncSessionLocal
from models import Post

router = APIRouter(prefix="/api/telegram", tags=["telegram"])

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "")


async def download_telegram_photo(file_id: str) -> str | None:
    """Download photo from Telegram and return URL or local path"""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}")
            data = resp.json()
            if data.get("ok"):
                file_path = data["result"]["file_path"]
                return f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
    except Exception:
        pass
    return None


def extract_title_and_content(text: str):
    """First line becomes title, rest is content"""
    if not text:
        return "Без заголовка", ""
    lines = text.strip().split("\n", 1)
    title = lines[0][:255]
    content = lines[1].strip() if len(lines) > 1 else lines[0]
    return title, content


@router.post("/webhook")
async def telegram_webhook(request: Request):
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    async with AsyncSessionLocal() as db:
        # Handle channel posts
        message = data.get("channel_post") or data.get("edited_channel_post")
        if not message:
            return {"ok": True}

        # Check if from our channel
        chat_id = str(message.get("chat", {}).get("id", ""))
        if CHANNEL_ID and chat_id != str(CHANNEL_ID):
            return {"ok": True}

        message_id = message.get("message_id")
        text = message.get("text") or message.get("caption") or ""
        is_edit = "edited_channel_post" in data

        # Get photo if present
        image_url = None
        photos = message.get("photo")
        if photos:
            largest = max(photos, key=lambda p: p.get("file_size", 0))
            image_url = await download_telegram_photo(largest["file_id"])

        title, content = extract_title_and_content(text)

        if is_edit:
            # Update existing post
            result = await db.execute(select(Post).where(Post.telegram_message_id == message_id))
            post = result.scalar_one_or_none()
            if post:
                post.title = title
                post.content = content
                if image_url:
                    post.image_url = image_url
                await db.commit()
        else:
            # Create new post (skip if no text)
            if not text and not photos:
                return {"ok": True}

            # Avoid duplicates
            existing = await db.scalar(select(Post).where(Post.telegram_message_id == message_id))
            if not existing:
                post = Post(
                    title=title,
                    content=content if content else title,
                    image_url=image_url,
                    telegram_message_id=message_id
                )
                db.add(post)
                await db.commit()

    return {"ok": True}


async def set_webhook(base_url: str):
    """Call this once to register webhook with Telegram"""
    webhook_url = f"{base_url}/api/telegram/webhook"
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook",
            params={"url": webhook_url}
        )
        return resp.json()
