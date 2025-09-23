# fastapi-account-manager

Plug-and-play account manager (UI + middleware) on top of `fastapi-authen`.

## Install
```bash
pip install fastapi-account-manager
# requires fastapi-authen==0.1.1


## USE:
from fastapi import FastAPI
from fastapi_account_manager import create_app
from fastapi_authen.seed import init_db, seed_super_admin

init_db(); seed_super_admin()   # once at startup / first run

app = FastAPI()
app.mount("/accounts", create_app())
