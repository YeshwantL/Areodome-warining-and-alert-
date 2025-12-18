from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from .. import auth

router = APIRouter(tags=["Pages"])
templates = Jinja2Templates(directory="app/templates")

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    # We can add auth check here or handle it in frontend (redirect if no token).
    # For better UX, let's just serve the page and let JS handle the data fetching/redirect.
    return templates.TemplateResponse("dashboard.html", {"request": request})

@router.get("/", response_class=HTMLResponse)
async def root_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@router.get("/change-password", response_class=HTMLResponse)
async def change_password_page(request: Request):
    return templates.TemplateResponse("change_password.html", {"request": request})
