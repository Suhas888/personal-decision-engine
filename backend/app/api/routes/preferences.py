from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from ...database.core import get_db
from ...models.core import Preference, User
from ...schemas.core import Preference as PreferenceSchema, PreferenceCreate
from ..dependencies import get_current_user

router = APIRouter()

@router.get("/", response_model=List[PreferenceSchema])
def get_preferences(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Preference).filter(Preference.user_id == current_user.id).all()

@router.put("/", response_model=PreferenceSchema)
def set_preference(pref: PreferenceCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_pref = db.query(Preference).filter(Preference.key == pref.key, Preference.user_id == current_user.id).first()
    if db_pref:
        db_pref.value = pref.value
    else:
        db_pref = Preference(**pref.model_dump(), user_id=current_user.id)
        db.add(db_pref)
    db.commit()
    db.refresh(db_pref)
    return db_pref
