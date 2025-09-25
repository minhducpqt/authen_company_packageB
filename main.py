from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# Routers
from routers.dashboard import router as dashboard_router

app = FastAPI(title="Dashboard Công ty — v20")

# Static (CSS/JS/IMG)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include routers
app.include_router(dashboard_router)

@app.get("/healthz")
def healthz():
    return {"ok": True}

# tiện để bạn chạy trực tiếp: python main.py
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8820, reload=False)
