from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from database import get_db
from models import Comment, Post, User
from auth import require_auth, get_current_user
from typing import Optional

router = APIRouter(prefix="/api/posts", tags=["comments"])


class CommentCreate(BaseModel):
    text: str


@router.get("/{post_id}/comments")
async def get_comments(post_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Comment)
        .where(Comment.post_id == post_id)
        .options(selectinload(Comment.user))
        .order_by(Comment.created_at.asc())
    )
    comments = result.scalars().all()
    return [
        {
            "id": c.id,
            "text": c.text,
            "created_at": c.created_at.isoformat(),
            "user": {"id": c.user.id, "username": c.user.username}
        }
        for c in comments
    ]


@router.post("/{post_id}/comments")
async def create_comment(
    post_id: int,
    data: CommentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    if not data.text.strip():
        raise HTTPException(status_code=400, detail="Comment cannot be empty")

    comment = Comment(user_id=current_user.id, post_id=post_id, text=data.text.strip())
    db.add(comment)
    await db.commit()
    await db.refresh(comment)

    return {
        "id": comment.id,
        "text": comment.text,
        "created_at": comment.created_at.isoformat(),
        "user": {"id": current_user.id, "username": current_user.username}
    }


@router.delete("/{post_id}/comments/{comment_id}")
async def delete_comment(
    post_id: int,
    comment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    comment = await db.get(Comment, comment_id)
    if not comment or comment.post_id != post_id:
        raise HTTPException(status_code=404, detail="Comment not found")

    if comment.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not allowed")

    await db.delete(comment)
    await db.commit()
    return {"ok": True}
