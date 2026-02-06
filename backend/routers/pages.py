import sys
import os
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import database, models

# Allow standalone execution
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.auth import auth

router = APIRouter(tags=["Pages"])
import os
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates"))

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request, db: Session = Depends(database.get_db)):
    user = await auth.get_user_from_session(request, db)
    if not user:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("dashboard.html", {"request": request, "user": user})

@router.get("/", response_class=HTMLResponse)
async def root_page(request: Request, db: Session = Depends(database.get_db)):
    user = await auth.get_user_from_session(request, db)
    if user:
        return RedirectResponse(url="/dashboard")
    return templates.TemplateResponse("login.html", {"request": request})

@router.get("/change-password", response_class=HTMLResponse)
async def change_password_page(request: Request, db: Session = Depends(database.get_db)):
    user = await auth.get_user_from_session(request, db)
    if not user:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("change_password.html", {"request": request, "user": user})
