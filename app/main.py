from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from . import models, database, tasks
from .routers import auth, alerts, chat, pages, admin

models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="Aerodrome Warning Alert System")

app.include_router(auth.router)
app.include_router(alerts.router)
app.include_router(chat.router)
app.include_router(pages.router)
app.include_router(admin.router)

@app.on_event("startup")
def start_scheduler():
    tasks.scheduler.start()

@app.on_event("shutdown")
def shutdown_scheduler():
    tasks.scheduler.shutdown()

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

@app.get("/")
def read_root():
    return {"message": "Aerodrome Warning System API is running"}

# Dependency
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()
