from fastapi import APIRouter, Depends
from pydantic import BaseModel
from ...services.llm_service import parse_natural_language, ParsedInputResponse
from sqlalchemy.orm import Session
from ...database.core import get_db
from ...models.core import Task, FixedEvent, UserProfile, TaskDependency, User
from ..dependencies import get_current_user

router = APIRouter()

class ParseRequest(BaseModel):
    text: str

@router.post("/parse", response_model=ParsedInputResponse)
def parse_input(request: ParseRequest, current_user: User = Depends(get_current_user)):
    return parse_natural_language(request.text)

@router.post("/save")
def save_parsed_data(data: ParsedInputResponse, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # 1. Save tasks and flush to get IDs
    created_tasks = []
    for t in data.tasks:
        task_data = t.model_dump(exclude={"depends_on"})
        db_task = Task(**task_data, user_id=current_user.id)
        db.add(db_task)
        created_tasks.append((t, db_task))
    db.flush()
    
    # 2. Build title-to-id mapping for dependencies
    existing_tasks = db.query(Task).filter(Task.user_id == current_user.id).all()
    title_map = {t.title.lower(): t.id for t in existing_tasks}
    
    # 3. Add dependencies
    for parsed_task, db_task in created_tasks:
        if parsed_task.depends_on:
            for dep_title in parsed_task.depends_on:
                dep_id = title_map.get(dep_title.lower())
                if dep_id:
                    db.add(TaskDependency(task_id=db_task.id, depends_on_task_id=dep_id, user_id=current_user.id))
    for e in data.fixed_events:
        db.add(FixedEvent(**e.model_dump(), user_id=current_user.id))
        
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.id).first()
    if not profile:
        profile = UserProfile(name=current_user.email.split("@")[0], user_id=current_user.id)
        db.add(profile)
        
    prefs = data.preferences.model_dump(exclude_none=True)
    for k, v in prefs.items():
        setattr(profile, k, v)
            
    db.commit()
    return {"ok": True}
