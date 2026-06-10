from fastapi import APIRouter

from app.api import auth, documents, health, logs, recommend, search, snapshot

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(documents.router)
api_router.include_router(health.router)
api_router.include_router(logs.router)
api_router.include_router(recommend.router)
api_router.include_router(search.router)
api_router.include_router(snapshot.router)
