from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi_account_manager.middlewares.auth_guard import AuthGuardMiddleware
from fastapi_account_manager.routers.auth import router as auth_router
from routers.dashboard import router as dashboard_router  # router sẵn có của bạn

app = FastAPI(title="Dashboard Công ty — v20")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Middleware chặn truy cập khi chưa login
app.add_middleware(AuthGuardMiddleware)

# Routers
app.include_router(auth_router)
app.include_router(dashboard_router)

@app.get("/healthz")
def healthz():
    return {"ok": True}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8820, reload=False)
