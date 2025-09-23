from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from fastapi_authen import current_user, require_roles, User
from fastapi_authen.deps import get_db
from fastapi_authen.models import User as UserModel, Session as RefreshSession
from fastapi_authen.security import hash_password
from ._shared import templates_dir
from ..services.account_service import build_username, ensure_ascii_username

router = APIRouter(tags=["accounts"])
templates = Jinja2Templates(directory=templates_dir())

@router.get("/users")
def list_users(request: Request, db: Session = Depends(get_db), me = Depends(current_user)):
    # SUPER_ADMIN => all; COMPANY_ADMIN => only within company_code
    q = db.query(UserModel)
    if me.role == "COMPANY_ADMIN":
        q = q.filter(UserModel.company_code == me.company_code)
    users = q.order_by(UserModel.id.desc()).all()
    return templates.TemplateResponse("accounts_list.html", {"request": request, "me": me, "users": users})

@router.get("/users/{user_id}")
def user_detail(user_id: int, request: Request, db: Session = Depends(get_db), me = Depends(current_user)):
    u = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    if me.role == "COMPANY_ADMIN" and u.company_code != me.company_code:
        raise HTTPException(status_code=403, detail="Forbidden")
    return templates.TemplateResponse("account_detail.html", {"request": request, "me": me, "u": u})

@router.post("/users/create")
def create_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    role: str = Form(...),    # e.g. "COMPANY_ADMIN" or "STAFF"
    db: Session = Depends(get_db),
        me=Depends(require_roles(["SUPER_ADMIN", "COMPANY_ADMIN"])),
):
    # normalize username (ascii, prefix with company_code if me is company admin)
    ensure_ascii_username(username)
    company_code = None

    if me.role == "COMPANY_ADMIN":
        if role == "SUPER_ADMIN":
            raise HTTPException(status_code=403, detail="COMPANY_ADMIN cannot create SUPER_ADMIN")
        company_code = me.company_code
        username = build_username(company_code, username)

    # SUPER_ADMIN may create across companies; expects full username or company_code explicitly supplied later.
    # For simplicity here, SUPER_ADMIN creates username as-is and can supply company_code via form (optional)
    if me.role == "SUPER_ADMIN":
        company_code = request.form()._dict.get("company_code") if hasattr(request, "form") else None

    if db.query(UserModel).filter(UserModel.username == username).first():
        raise HTTPException(status_code=400, detail="Username already exists")

    u = UserModel(
        username=username,
        password_hash=hash_password(password),
        role=role,
        company_code=company_code,
        is_active=True,
        token_version=0,
    )
    db.add(u); db.commit()
    return RedirectResponse(url="/accounts/users", status_code=303)

@router.post("/users/{user_id}/enable")
def enable_user(user_id: int, db: Session = Depends(get_db), actor: User = Depends(require_roles(["SUPER_ADMIN", "COMPANY_ADMIN"]))):
    target = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if actor.id == target.id:
        raise HTTPException(status_code=400, detail="Cannot enable yourself")  # self-protection symmetry
    if actor.role == "COMPANY_ADMIN":
        if target.role == "SUPER_ADMIN" or target.company_code != actor.company_code:
            raise HTTPException(status_code=403, detail="Forbidden")
    target.is_active = True
    db.add(target); db.commit()
    return RedirectResponse(url=f"/accounts/users/{user_id}", status_code=303)

@router.post("/users/{user_id}/disable")
def disable_user(user_id: int, db: Session = Depends(get_db), actor: User = Depends(require_roles(["SUPER_ADMIN", "COMPANY_ADMIN"]))):
    target = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if actor.id == target.id:
        raise HTTPException(status_code=400, detail="Cannot disable yourself")
    if actor.role == "COMPANY_ADMIN":
        if target.role == "SUPER_ADMIN" or target.company_code != actor.company_code:
            raise HTTPException(status_code=403, detail="Forbidden")
    target.is_active = False
    target.token_version += 1
    db.query(RefreshSession).filter(
        RefreshSession.user_id == target.id,
        RefreshSession.revoked_at.is_(None)
    ).update({RefreshSession.revoked_at: __import__("datetime").datetime.utcnow()}, synchronize_session=False)
    db.add(target); db.commit()
    return RedirectResponse(url=f"/accounts/users/{user_id}", status_code=303)

@router.post("/users/{user_id}/force_password")
def force_password(
    user_id: int,
    new_password: str = Form(...),
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(["SUPER_ADMIN", "COMPANY_ADMIN"]))
):
    target = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if actor.role == "COMPANY_ADMIN":
        if target.role == "SUPER_ADMIN" or target.company_code != actor.company_code:
            raise HTTPException(status_code=403, detail="Forbidden")
    target.password_hash = hash_password(new_password)
    target.token_version += 1
    db.query(RefreshSession).filter(
        RefreshSession.user_id == target.id,
        RefreshSession.revoked_at.is_(None)
    ).update({RefreshSession.revoked_at: __import__("datetime").datetime.utcnow()}, synchronize_session=False)
    db.add(target); db.commit()
    return RedirectResponse(url=f"/accounts/users/{user_id}", status_code=303)

@router.get("/me/change_password")
def change_password_form(request: Request, me = Depends(current_user)):
    return templates.TemplateResponse("change_password.html", {"request": request, "me": me})
