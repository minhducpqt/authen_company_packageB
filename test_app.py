from fastapi import FastAPI
from fastapi_authen.seed import init_db, seed_super_admin
from fastapi_authen import auth_router
from fastapi_account_manager import create_app
import uvicorn

init_db(); seed_super_admin()

app = FastAPI(title="Demo with Account Manager B")
app.mount("/accounts", create_app())              # B (UI/middleware) → /accounts/*
app.include_router(auth_router, prefix="/auth")   # A (API) → /auth/*

if __name__ == "__main__":
    uvicorn.run("test_app:app", host="0.0.0.0", port=8201, reload=True)
