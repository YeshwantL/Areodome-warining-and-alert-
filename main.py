from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import models, database, tasks
from routers import auth, alerts, chat, pages, admin, prediction

models.Base.metadata.create_all(bind=database.engine)

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    tasks.scheduler.start()
    yield
    # Shutdown
    tasks.scheduler.shutdown()

app = FastAPI(title="Aerodrome Warning Alert System", lifespan=lifespan)

app.include_router(auth.router, prefix="/auth")
app.include_router(alerts.router)
app.include_router(chat.router)
app.include_router(pages.router)
app.include_router(admin.router)
app.include_router(prediction.router)

import os
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

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
