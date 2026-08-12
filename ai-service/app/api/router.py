from fastapi import APIRouter
from ai_service.app.api.v1 import analyze

api_v1_router = APIRouter()

api_v1_router.include_router(analyze.router, tags=["analysis"])