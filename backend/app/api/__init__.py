from fastapi import APIRouter

from app.api import collectors, datasets, health, import_data, indexing, research, settings

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(datasets.router)
api_router.include_router(import_data.router)
api_router.include_router(indexing.router)
api_router.include_router(research.router)
api_router.include_router(settings.router)
api_router.include_router(collectors.router)
