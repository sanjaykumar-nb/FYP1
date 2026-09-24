from fastapi import APIRouter
from app.api.v1 import auth, github, organizations, projects, tasks, meetings, analytics, admin, websocket

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(organizations.router, prefix="/organizations", tags=["organizations"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(tasks.router, prefix="/projects/{project_id}/tasks", tags=["tasks"])
api_router.include_router(meetings.router, prefix="/projects/{project_id}/meetings", tags=["meetings"])
api_router.include_router(github.router, prefix="/projects/{project_id}/github", tags=["github"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(websocket.router, prefix="/ws", tags=["websocket"])