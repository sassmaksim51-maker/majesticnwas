from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from database import get_db
from models import Favorite, Post
from auth import require_auth
from models import User

router = APIRouter(prefix="/api", tags=["favorites"])


@router.post("/posts/{post_id}/favorite")
async def toggle_favorite(post_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_auth)):
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    existing = await db.scalar(select(Favorite).where(Favorite.user_id == current_user.id, Favorite.post_id == post_id))

    if existing:
        await db.delete(existing)
        await db.commit()
        return {"favorited": False}
    else:
        fav = Favorite(user_id=current_user.id, post_id=post_id)
        db.add(fav)
        await db.commit()
        return {"favorited": True}


@router.get("/users/me/favorites")
async def get_my_favorites(db: AsyncSession = Depends(get_db), current_user: User = Depends(require_auth)):
    result = await db.execute(
        select(Favorite)
        .where(Favorite.user_id == current_user.id)
        .options(selectinload(Favorite.post))
        .order_by(Favorite.created_at.desc())
    )
    favorites = result.scalars().all()
    return [
        {
            "id": f.post.id,
            "title": f.post.title,
            "content": f.post.content[:200] + "..." if len(f.post.content) > 200 else f.post.content,
            "image_url": f.post.image_url,
            "created_at": f.post.created_at.isoformat(),
        }
        for f in favorites
    ]
