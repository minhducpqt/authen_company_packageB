from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi_authen.models import User as UserModel

def count_users_per_company(db: Session):
    return db.query(UserModel.company_code, func.count(UserModel.id)).group_by(UserModel.company_code).all()
