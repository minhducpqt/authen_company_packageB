# main.py (chỉ thêm 1 dòng include)
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi_account_manager.middlewares.auth_guard import AuthGuardMiddleware
from fastapi_account_manager.routers.auth import router as auth_router
from routers.dashboard import router as dashboard_router
from routers.account import router as account_router   # <-- thêm
from fastapi.responses import RedirectResponse

app = FastAPI(title="Dashboard Công ty — v20")
app.mount("/static", StaticFiles(directory="static"), name="static")
app.add_middleware(AuthGuardMiddleware)

app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(account_router)  # <-- thêm

@app.get("/healthz")
def healthz():
    return {"ok": True}

@app.get("/tien-ich-khac")
def _legacy_tools_redirect():
    return RedirectResponse(url="/account", status_code=303)

@app.get("/quan-ly-tai-khoan")
def _legacy_account_redirect():
    return RedirectResponse(url="/account", status_code=303)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8820, reload=True)
