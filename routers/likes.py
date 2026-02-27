from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from models import Like, Post, User
from auth import require_auth

router = APIRouter(prefix="/api/posts", tags=["likes"])


@router.post("/{post_id}/like")
async def toggle_like(post_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_auth)):
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    existing = await db.scalar(select(Like).where(Like.user_id == current_user.id, Like.post_id == post_id))

    if existing:
        await db.delete(existing)
        await db.commit()
        return {"liked": False}
    else:
        like = Like(user_id=current_user.id, post_id=post_id)
        db.add(like)
        await db.commit()
        return {"liked": True}
