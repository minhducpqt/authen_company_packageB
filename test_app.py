# test_app.py
from fastapi import FastAPI
from fastapi_authen.seed import init_db, seed_super_admin
from fastapi_authen import auth_router
from fastapi_account_manager import create_app
import uvicorn

# --- Init schema & seed (chỉ cần chạy 1 lần mỗi môi trường) ---
init_db()
seed_super_admin()  # tạo super admin mặc định: ducluu / 123456

# --- Main application ---
app = FastAPI(title="Demo with Account Manager B")

# Mount Module B (UI + middleware) tại /accounts
account_app = create_app()
app.mount("/accounts", account_app)

# Mount Module A (auth API) tại /auth
app.include_router(auth_router, prefix="/auth")

# --- Run directly (for PyCharm Run/Debug or python3 test_app.py) ---
if __name__ == "__main__":
    uvicorn.run("test_app:app", host="0.0.0.0", port=8001, reload=True)
