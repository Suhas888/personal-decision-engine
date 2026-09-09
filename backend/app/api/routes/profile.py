from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ...database.core import get_db
from ...models.core import UserProfile, User
from ...schemas.core import UserProfile as UserProfileSchema, UserProfileCreate
from ..dependencies import get_current_user

router = APIRouter()


@router.post("/profile", response_model=UserProfileSchema)
def create_profile(profile: UserProfileCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_profile = UserProfile(**profile.model_dump(), user_id=current_user.id)
    db.add(db_profile)
    db.commit()
    db.refresh(db_profile)
    return db_profile


@router.get("/profile", response_model=UserProfileSchema)
def get_profile(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.id).first()
    if profile is None:
        default = UserProfileCreate(name=current_user.email.split("@")[0])
        return create_profile(default, db, current_user)
    return profile
