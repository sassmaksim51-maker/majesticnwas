from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from typing import Optional
from database import get_db
from models import Post, Like, Comment, Favorite, User
from auth import require_admin, get_current_user

router = APIRouter(prefix="/api/posts", tags=["posts"])


class PostCreate(BaseModel):
    title: str
    content: str
    image_url: Optional[str] = None


class PostUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    image_url: Optional[str] = None


async def post_to_dict(post: Post, db: AsyncSession, current_user: Optional[User] = None):
    likes_count = await db.scalar(select(func.count()).where(Like.post_id == post.id))
    comments_count = await db.scalar(select(func.count()).where(Comment.post_id == post.id))

    is_liked = False
    is_favorited = False
    if current_user:
        like = await db.scalar(select(Like).where(Like.user_id == current_user.id, Like.post_id == post.id))
        is_liked = like is not None
        fav = await db.scalar(select(Favorite).where(Favorite.user_id == current_user.id, Favorite.post_id == post.id))
        is_favorited = fav is not None

    return {
        "id": post.id,
        "title": post.title,
        "content": post.content,
        "image_url": post.image_url,
        "created_at": post.created_at.isoformat(),
        "updated_at": post.updated_at.isoformat(),
        "likes_count": likes_count,
        "comments_count": comments_count,
        "is_liked": is_liked,
        "is_favorited": is_favorited,
    }


@router.get("")
async def get_posts(
    page: int = 1,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    offset = (page - 1) * limit
    total = await db.scalar(select(func.count()).select_from(Post))
    result = await db.execute(select(Post).order_by(Post.created_at.desc()).offset(offset).limit(limit))
    posts = result.scalars().all()

    posts_data = []
    for post in posts:
        posts_data.append(await post_to_dict(post, db, current_user))

    return {
        "posts": posts_data,
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit
    }


@router.get("/{post_id}")
async def get_post(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return await post_to_dict(post, db, current_user)


@router.post("")
async def create_post(data: PostCreate, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    post = Post(**data.model_dump())
    db.add(post)
    await db.commit()
    await db.refresh(post)
    return await post_to_dict(post, db, admin)


@router.put("/{post_id}")
async def update_post(post_id: int, data: PostUpdate, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(post, field, value)
    await db.commit()
    await db.refresh(post)
    return await post_to_dict(post, db, admin)


@router.delete("/{post_id}")
async def delete_post(post_id: int, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    await db.delete(post)
    await db.commit()
    return {"ok": True}
