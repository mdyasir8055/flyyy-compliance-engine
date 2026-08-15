from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine
from app import models  # noqa: F401 - ensures models are registered before create_all
from app.routers import policies, controls, scans, dashboard

app = FastAPI(title="FLYYY.AI Compliance API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)


@app.get("/api/health")
def health():
    return {"status": "ok"}


app.include_router(policies.router)
app.include_router(controls.router)
app.include_router(scans.router)
app.include_router(dashboard.router)
