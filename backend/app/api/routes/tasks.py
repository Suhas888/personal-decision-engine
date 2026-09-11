from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from ...database.core import get_db
from ...models.core import Task, TaskDependency, User
from ...schemas.core import Task as TaskSchema, TaskCreate
from ..dependencies import get_current_user

router = APIRouter()

def _check_circular_dependencies(db: Session, proposed_task_id: int, proposed_deps: List[int], user_id: str):
    # Fetch all current dependencies for user's tasks
    user_tasks = db.query(Task.id).filter(Task.user_id == user_id).subquery()
    all_deps = db.query(TaskDependency).filter(TaskDependency.task_id.in_(user_tasks)).all()
    
    # Build graph: node -> list of dependencies (edges point from dependent to prerequisite)
    # A cycle means A depends on B, B depends on A
    graph = {}
    for d in all_deps:
        if d.task_id == proposed_task_id:
            continue # We will inject the proposed ones
        if d.task_id not in graph:
            graph[d.task_id] = []
        graph[d.task_id].append(d.depends_on_task_id)
        
    graph[proposed_task_id] = proposed_deps
    
    # DFS cycle detection
    visited = set()
    rec_stack = set()
    
    def dfs(node):
        visited.add(node)
        rec_stack.add(node)
        
        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                if dfs(neighbor):
                    return True
            elif neighbor in rec_stack:
                return True
                
        rec_stack.remove(node)
        return False
        
    for node in graph.keys():
        if node not in visited:
            if dfs(node):
                return True
    return False


@router.get("/", response_model=List[TaskSchema])
def get_tasks(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    tasks = db.query(Task).filter(Task.user_id == current_user.id).all()
    # To get dependencies, we filter by tasks that belong to the user
    task_ids = [t.id for t in tasks]
    deps = db.query(TaskDependency).filter(TaskDependency.task_id.in_(task_ids)).all()
    
    dep_map = {}
    for d in deps:
        if d.task_id not in dep_map:
            dep_map[d.task_id] = []
        dep_map[d.task_id].append(d.depends_on_task_id)
        
    result = []
    for t in tasks:
        t_dict = {c.name: getattr(t, c.name) for c in t.__table__.columns}
        t_dict["dependencies"] = dep_map.get(t.id, [])
        result.append(t_dict)
    return result


@router.post("/", response_model=TaskSchema)
def create_task(task: TaskCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    task_data = task.model_dump(exclude={"dependencies"})
    db_task = Task(**task_data, user_id=current_user.id)
    db.add(db_task)
    db.flush() # get ID
    
    if task.dependencies:
        if _check_circular_dependencies(db, db_task.id, task.dependencies, current_user.id):
            db.rollback()
            raise HTTPException(status_code=400, detail="Circular dependency detected")
            
        for dep_id in task.dependencies:
            db.add(TaskDependency(task_id=db_task.id, depends_on_task_id=dep_id))
            
    db.commit()
    db.refresh(db_task)
    
    res = {c.name: getattr(db_task, c.name) for c in db_task.__table__.columns}
    res["dependencies"] = task.dependencies or []
    return res


@router.put("/{task_id}", response_model=TaskSchema)
def update_task(task_id: int, task: TaskCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_task = db.query(Task).filter(Task.id == task_id, Task.user_id == current_user.id).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
        
    task_data = task.model_dump(exclude={"dependencies"})
    for key, value in task_data.items():
        setattr(db_task, key, value)
        
    if task.dependencies is not None:
        if _check_circular_dependencies(db, task_id, task.dependencies, current_user.id):
            raise HTTPException(status_code=400, detail="Circular dependency detected")
            
        # Delete old deps
        db.query(TaskDependency).filter(TaskDependency.task_id == task_id).delete()
        
        # Add new deps
        for dep_id in task.dependencies:
            db.add(TaskDependency(task_id=task_id, depends_on_task_id=dep_id))
            
    db.commit()
    db.refresh(db_task)
    
    # Return updated
    res = {c.name: getattr(db_task, c.name) for c in db_task.__table__.columns}
    # fetch active deps
    current_deps = [d.depends_on_task_id for d in db.query(TaskDependency).filter(TaskDependency.task_id == task_id).all()]
    res["dependencies"] = current_deps
    return res

@router.delete("/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_task = db.query(Task).filter(Task.id == task_id, Task.user_id == current_user.id).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Delete related dependencies
    db.query(TaskDependency).filter(
        ((TaskDependency.task_id == task_id) | (TaskDependency.depends_on_task_id == task_id))
    ).delete(synchronize_session=False)
    
    db.delete(db_task)
    db.commit()
    return {"ok": True}

from pydantic import BaseModel
class TaskCompleteUpdate(BaseModel):
    completed: bool

@router.patch("/{task_id}/complete")
def toggle_task_completion(task_id: int, update: TaskCompleteUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_task = db.query(Task).filter(Task.id == task_id, Task.user_id == current_user.id).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
        
    db_task.completed = update.completed
    db.commit()
    db.refresh(db_task)
    return {"id": db_task.id, "completed": db_task.completed}
