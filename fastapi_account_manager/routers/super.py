from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func

from fastapi_authen import require_roles, User
from fastapi_authen.deps import get_db
from fastapi_authen.models import User as UserModel
from ._shared import templates_dir

router = APIRouter(tags=["super-admin"])
templates = Jinja2Templates(directory=templates_dir())

@router.get("/super")
def super_home(request: Request, db: Session = Depends(get_db), me = Depends(require_roles(["SUPER_ADMIN"]))):
    # thống kê: số user per company
    rows = (
        db.query(UserModel.company_code, func.count(UserModel.id))
        .group_by(UserModel.company_code)
        .order_by(UserModel.company_code)
        .all()
    )
    # danh sách admin toàn hệ thống
    admins = db.query(UserModel).filter(UserModel.role == "COMPANY_ADMIN").order_by(UserModel.company_code, UserModel.username).all()
    return templates.TemplateResponse("dashboard.html", {"request": request, "me": me, "company_counts": rows, "admins": admins})
