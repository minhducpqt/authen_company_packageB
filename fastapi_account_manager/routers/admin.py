from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from fastapi_authen import current_user, require_roles, User
from fastapi_authen.deps import get_db
from fastapi_authen.models import User as UserModel
from ._shared import templates_dir

router = APIRouter(tags=["company-admin"])
templates = Jinja2Templates(directory=templates_dir())

@router.get("/admin")
def admin_home(request: Request, db: Session = Depends(get_db), me = Depends(require_roles(["COMPANY_ADMIN"]))):
    # thống kê nhanh trong company
    total_users = db.query(UserModel).filter(UserModel.company_code == me.company_code).count()
    admins = db.query(UserModel).filter(UserModel.company_code == me.company_code, UserModel.role == "COMPANY_ADMIN").count()
    return templates.TemplateResponse("dashboard.html", {"request": request, "me": me, "stat_total": total_users, "stat_admins": admins})
