from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from typing import Dict, Set
from uuid import UUID
from app.core.security import decode_token

router = APIRouter()

# Connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[UUID, Set[WebSocket]] = {}
        self.user_connections: Dict[UUID, Set[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, project_id: UUID, user_id: UUID):
        await websocket.accept()
        if project_id not in self.active_connections:
            self.active_connections[project_id] = set()
        self.active_connections[project_id].add(websocket)
        
        if user_id not in self.user_connections:
            self.user_connections[user_id] = set()
        self.user_connections[user_id].add(websocket)
    
    def disconnect(self, websocket: WebSocket, project_id: UUID, user_id: UUID):
        if project_id in self.active_connections:
            self.active_connections[project_id].discard(websocket)
            if not self.active_connections[project_id]:
                del self.active_connections[project_id]
        
        if user_id in self.user_connections:
            self.user_connections[user_id].discard(websocket)
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]
    
    async def send_personal_message(self, message: dict, user_id: UUID):
        if user_id in self.user_connections:
            for connection in self.user_connections[user_id]:
                try:
                    await connection.send_json(message)
                except:
                    pass
    
    async def broadcast_to_project(self, message: dict, project_id: UUID):
        if project_id in self.active_connections:
            for connection in self.active_connections[project_id]:
                try:
                    await connection.send_json(message)
                except:
                    pass


manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
):
    # Authenticate user
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        await websocket.close(code=4001, reason="Invalid token")
        return
    
    user_id = UUID(payload.get("sub"))
    org_id = UUID(payload.get("org_id"))
    
    # Get project_id from query params
    project_id_str = websocket.query_params.get("project_id")
    if not project_id_str:
        await websocket.close(code=4002, reason="Missing project_id")
        return
    
    project_id = UUID(project_id_str)
    
    await manager.connect(websocket, project_id, user_id)
    
    try:
        while True:
            data = await websocket.receive_json()
            
            # A connection is bound to one project for its whole lifetime (see
            # manager.connect above) — switching to another project would
            # require re-registering the connection, which isn't implemented.
            # Say so explicitly rather than silently accepting and doing
            # nothing.
            if data.get("type") == "subscribe":
                await websocket.send_json({
                    "type": "error",
                    "message": "Subscribing to additional projects is not supported; open a new connection instead.",
                })

            elif data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    
    except WebSocketDisconnect:
        manager.disconnect(websocket, project_id, user_id)


# Functions to broadcast events (called from other parts of the application)
async def broadcast_task_updated(project_id: UUID, task_data: dict):
    await manager.broadcast_to_project({
        "event": "task.updated",
        "data": task_data,
        "project_id": str(project_id),
    }, project_id)


async def broadcast_task_created(project_id: UUID, task_data: dict):
    await manager.broadcast_to_project({
        "event": "task.created",
        "data": task_data,
        "project_id": str(project_id),
    }, project_id)


async def broadcast_risk_updated(project_id: UUID, risk_data: dict):
    await manager.broadcast_to_project({
        "event": "risk.updated",
        "data": risk_data,
        "project_id": str(project_id),
    }, project_id)


async def broadcast_recommendation_created(project_id: UUID, rec_data: dict):
    await manager.broadcast_to_project({
        "event": "recommendation.created",
        "data": rec_data,
        "project_id": str(project_id),
    }, project_id)


async def broadcast_notification(user_id: UUID, notification_data: dict):
    await manager.send_personal_message({
        "event": "notification.new",
        "data": notification_data,
    }, user_id)


async def broadcast_analysis_started(project_id: UUID, run_data: dict):
    await manager.broadcast_to_project({
        "event": "analysis.started",
        "data": run_data,
        "project_id": str(project_id),
    }, project_id)


async def broadcast_analysis_completed(project_id: UUID, run_data: dict):
    await manager.broadcast_to_project({
        "event": "analysis.completed",
        "data": run_data,
        "project_id": str(project_id),
    }, project_id)


async def broadcast_analysis_failed(project_id: UUID, error_data: dict):
    await manager.broadcast_to_project({
        "event": "analysis.failed",
        "data": error_data,
        "project_id": str(project_id),
    }, project_id)