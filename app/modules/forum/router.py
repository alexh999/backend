from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.forum.schemas import ForumPostCreateRequest, ForumPostListResponse, ForumPostResponse
from app.modules.forum.service import create_post, list_my_posts, list_public_posts, to_post_response
from app.modules.users.models import User, UserRole


router = APIRouter(prefix="/forum", tags=["forum"])


@router.get("/posts", response_model=ForumPostListResponse)
def read_public_forum_posts(
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ForumPostListResponse:
    return ForumPostListResponse(
        items=[to_post_response(post) for post in list_public_posts(db, limit=limit)]
    )


@router.get("/me/posts", response_model=ForumPostListResponse)
def read_my_forum_posts(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ForumPostListResponse:
    return ForumPostListResponse(
        items=[to_post_response(post) for post in list_my_posts(db, author=current_user, limit=limit)]
    )


@router.post("/posts", response_model=ForumPostResponse, status_code=status.HTTP_201_CREATED)
def create_forum_post(
    request: ForumPostCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ForumPostResponse:
    if current_user.role != UserRole.USER:
        # Admin content should go through moderation tools, not the app forum flow.
        from fastapi import HTTPException

        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Regular user access required.")
    post = create_post(
        db,
        author=current_user,
        content=request.content,
        topic_label=request.topic_label,
    )
    return to_post_response(post)
