from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from ...database.core import get_db
from ...models.core import FixedEvent, User
from ...schemas.plan import FixedEvent as FixedEventSchema, FixedEventCreate
from ..dependencies import get_current_user

router = APIRouter()


@router.get("/", response_model=List[FixedEventSchema])
def get_events(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(FixedEvent).filter(FixedEvent.user_id == current_user.id).all()


@router.post("/", response_model=FixedEventSchema)
def create_event(event: FixedEventCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    event_data = event.model_dump()
    db_event = FixedEvent(**event_data, user_id=current_user.id)
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    return db_event


@router.put("/{event_id}", response_model=FixedEventSchema)
def update_event(event_id: int, event: FixedEventCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    from fastapi import HTTPException
    db_event = db.query(FixedEvent).filter(FixedEvent.id == event_id, FixedEvent.user_id == current_user.id).first()
    if not db_event:
        raise HTTPException(status_code=404, detail="Event not found")
    for key, value in event.model_dump().items():
        setattr(db_event, key, value)
    db.commit()
    db.refresh(db_event)
    return db_event

@router.delete("/{event_id}")
def delete_event(event_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    from fastapi import HTTPException
    db_event = db.query(FixedEvent).filter(FixedEvent.id == event_id, FixedEvent.user_id == current_user.id).first()
    if not db_event:
        raise HTTPException(status_code=404, detail="Event not found")
    db.delete(db_event)
    db.commit()
    return {"ok": True}
