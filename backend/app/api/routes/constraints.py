from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime, timezone

from ...database.core import get_db
from ...models.core import DynamicConstraint, UserProfile, User
from ...schemas.constraints import ConstraintIR
from ...services.validators import ConstraintValidator, ConstraintConflictDetector
from ...services.llm_service import parse_constraints_from_text

from ..dependencies import get_current_user

router = APIRouter()

class PreviewConstraintRequest(BaseModel):
    message: str

class ApplyConstraintRequest(BaseModel):
    constraint: ConstraintIR

@router.get("/", response_model=List[Dict[str, Any]])
def get_constraints(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    constraints = db.query(DynamicConstraint).filter(DynamicConstraint.user_id == current_user.id).all()
    return [
        {
            "id": c.id,
            "type": c.type,
            "scope": c.scope,
            "target": c.target,
            "parameters": c.parameters,
            "strength": c.strength,
            "enabled": c.enabled,
            "source": c.source
        } for c in constraints
    ]

@router.get("/{id}")
def get_constraint(id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    c = db.query(DynamicConstraint).filter(
        DynamicConstraint.id == id,
        DynamicConstraint.user_id == current_user.id
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail="Constraint not found")
    return {
        "id": c.id,
        "type": c.type,
        "scope": c.scope,
        "target": c.target,
        "parameters": c.parameters,
        "strength": c.strength,
        "enabled": c.enabled,
        "source": c.source
    }

@router.post("/")
def create_constraint(request: ApplyConstraintRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    validator = ConstraintValidator()
    val = validator.validate([request.constraint])
    if not val.is_valid:
        raise HTTPException(status_code=422, detail="Invalid constraint representation")
        
    c = DynamicConstraint(
        user_id=current_user.id,
        type=request.constraint.type.value,
        scope=request.constraint.scope.value,
        target=request.constraint.target_identifier,
        parameters=request.constraint.parameters,
        strength=request.constraint.strength.value,
        enabled=True,
        source="SYSTEM"
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return {"id": c.id, "status": "created"}

@router.delete("/{id}")
def delete_constraint(id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    c = db.query(DynamicConstraint).filter(
        DynamicConstraint.id == id,
        DynamicConstraint.user_id == current_user.id
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail="Constraint not found")
    db.delete(c)
    db.commit()
    return {"status": "deleted"}

@router.patch("/{id}/enable")
def toggle_constraint(id: int, enabled: bool, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    c = db.query(DynamicConstraint).filter(
        DynamicConstraint.id == id,
        DynamicConstraint.user_id == current_user.id
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail="Constraint not found")
    c.enabled = True
    c.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "enabled"}

@router.patch("/{id}/disable")
def disable_constraint(id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    c = db.query(DynamicConstraint).filter(
        DynamicConstraint.id == id,
        DynamicConstraint.user_id == current_user.id
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail="Constraint not found")
    c.enabled = False
    c.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "disabled"}

@router.post("/preview")
def preview_constraint(req: PreviewConstraintRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        parsed_constraints = parse_constraints_from_text(req.message)
    except Exception as e:
        # LLM parsing failed entirely or explicitly flagged as unsupported
        # We catch unsupported logic cleanly
        return {
            "supported": False,
            "clarification_needed": True,
            "reason": str(e)
        }
        
    if not parsed_constraints:
        return {
            "supported": False,
            "clarification_needed": True,
            "reason": "Could not identify a clear, supported rule in your request."
        }
        
    for ir in parsed_constraints:
        validator = ConstraintValidator()
        validation = validator.validate([ir])
        if not validation.is_valid:
            return {"supported": False, "clarification_needed": True, "clarification_question": f"Unsupported or invalid constraint: {validation.errors}"}
        
    # 2. Conflict Detection
    existing_records = db.query(DynamicConstraint).filter(
        DynamicConstraint.user_id == current_user.id,
        DynamicConstraint.enabled == True
    ).all()
    
    existing_irs = []
    for r in existing_records:
        try:
            existing_irs.append(ConstraintIR(
                type=r.type,
                scope=r.scope,
                target_identifier=r.target,
                parameters=r.parameters,
                strength=r.strength
            ))
        except:
            pass

    detector = ConstraintConflictDetector()
    val_res = detector.detect(existing_irs + [ir])
    conflicts = val_res.errors
    
    if conflicts:
        return {
            "supported": True,
            "constraint": ir.model_dump(),
            "summary": "Constraint interpreted successfully but conflicts with existing rules.",
            "conflicts": conflicts
        }
        
    return {
        "supported": True,
        "constraint": ir.model_dump(),
        "summary": "Rule is supported and no conflicts were found.",
        "conflicts": []
    }

@router.post("/apply")
def apply_constraint(req: ApplyConstraintRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Same validation
    validator = ConstraintValidator()
    existing_records = db.query(DynamicConstraint).filter(
        DynamicConstraint.user_id == current_user.id,
        DynamicConstraint.enabled == True
    ).all()
    
    existing_irs = []
    for r in existing_records:
        try:
            existing_irs.append(ConstraintIR(
                type=r.type,
                scope=r.scope,
                target_identifier=r.target,
                parameters=r.parameters,
                strength=r.strength
            ))
        except:
            pass

    detector = ConstraintConflictDetector()
    val_res = detector.detect(existing_irs + [req.constraint])
    conflicts = val_res.errors
    
    if conflicts:
        raise HTTPException(status_code=409, detail=f"Cannot apply due to conflicts: {conflicts}")

    c = DynamicConstraint(
        user_id=current_user.id,
        type=req.constraint.type.value,
        scope=req.constraint.scope.value,
        target=req.constraint.target_identifier,
        parameters=req.constraint.parameters,
        strength=req.constraint.strength.value,
        enabled=True,
        source="LLM"
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return {"id": c.id, "status": "applied"}
