from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import models, database
from app.tasks import tasks
from routers import authentication as auth, alerts, chat, pages, admin, prediction

models.Base.metadata.create_all(bind=database.engine)

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    tasks.scheduler.start()
    yield
    # Shutdown
    tasks.scheduler.shutdown()

from fastapi.middleware.gzip import GZipMiddleware

app = FastAPI(title="Aerodrome Warning Alert System", lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=1000)

from starlette.middleware.sessions import SessionMiddleware
import os
# Use a strong secret key, preferably from env
SECRET_KEY = os.getenv("SECRET_KEY", "supersecretkeychangeinproduction")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, max_age=86400*7) # 7 days session

app.include_router(auth.router, prefix="/auth")
app.include_router(alerts.router)
app.include_router(chat.router)
app.include_router(pages.router)
app.include_router(admin.router)
app.include_router(prediction.router)

import os
# Adjusted for backend logic: static is in ../../static relative to backend/app/main.py
# Or relative to the working directory /app (which is backend/) -> ../static is outside?
# Let's rely on relative path from this file.
# app/main.py -> dirname is app/ -> join with ../../static -> ../static relative to backend.
# Wait, structure is backend/app/main.py. Standard static is now served by Nginx in Prod.
# For local dev (python backend/app/main.py), we need to find it.
# Project root: backend/.. -> static/
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "static")), name="static")
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

if __name__ == "__main__":
    import uvicorn
    import os
    
    # Check for SSL certificates
    key_file = "key.pem"
    cert_file = "cert.pem"
    
    if os.path.exists(key_file) and os.path.exists(cert_file):
        print("SSL Certificates found. Running in HTTPS mode.")
        uvicorn.run(
            "main:app", 
            host="0.0.0.0", 
            port=8000, 
            reload=True,
            ssl_keyfile=key_file, 
            ssl_certfile=cert_file
        )
    else:
        print("Warning: SSL Certificates not found. Running in HTTP mode.")
        uvicorn.run(
            "main:app", 
            host="0.0.0.0", 
            port=8000, 
            reload=True
        )
