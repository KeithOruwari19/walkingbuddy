"""
Room Routes.py
Sinthujan Jayaranjan

This file handles all the room-related operations which include:
- Creating new walking rooms
- Listing available rooms
- Joining existing rooms
- Updating room status
"""

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Request
from pydantic import BaseModel
from typing import List
import uuid
import asyncio
import json

from .database import RoomDatabase

router = APIRouter(prefix="/api/rooms", tags=["rooms"])

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        try:
            self.active_connections.remove(websocket)
        except ValueError:
            pass

    async def broadcast(self, message: dict):
        if not self.active_connections:
            return
        text = json.dumps(message)
        coros = [ws.send_text(text) for ws in list(self.active_connections)]
        await asyncio.gather(*coros, return_exceptions=True)

manager = ConnectionManager()

class CreateRoomRequest(BaseModel):
    user_id: str
    destination: str
    start_coord: List[float]
    dest_coord: List[float]
    max_members: int = 10

class JoinRoomRequest(BaseModel):
    user_id: str
    room_id: str

class LeaveRoomRequest(BaseModel):
    user_id: str
    room_id: str

class UpdateRoomStatusRequest(BaseModel):
    room_id: str
    status: str

async def emit_room_event(event_type: str, room: dict):
    payload = {"type": event_type, "room": room}
    await manager.broadcast(payload)

@router.post("/create")
async def create_room(req: CreateRoomRequest):
    try:
        room_id = str(uuid.uuid4())[:8]
        room = RoomDatabase.create_room(
            room_id=room_id,
            creator_id=req.user_id,
            destination=req.destination,
            start_coord=req.start_coord,
            dest_coord=req.dest_coord,
            max_members=req.max_members,
        )
        # broadcast the new room
        await emit_room_event("room:new", room)
        return {"success": True, "room": room, "message": f"Room {room_id} created."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/list")
def list_rooms():
    rooms = RoomDatabase.get_active_rooms()
    return {"success": True, "rooms": rooms}

@router.post("/join")
async def join_room(req: JoinRoomRequest):
    try:
        room = RoomDatabase.join_room(req.room_id, req.user_id)
        # broadcast join event
        await emit_room_event("room:join", room)
        return {
            "success": True,
            "room": room,
            "message": f"User {req.user_id} joined room {req.room_id}.",
        }
    except ValueError as e:
        if "not found" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        else:
            raise HTTPException(status_code=400, detail=str(e))

@router.post("/leave")
async def leave_room(req: LeaveRoomRequest):
    try:
        room = RoomDatabase.leave_room(req.room_id, req.user_id)
        await emit_room_event("room:leave", room)
        return {
            "success": True,
            "room": room,
            "message": f"User {req.user_id} left room {req.room_id}.",
        }
    except ValueError as e:
        if "not found" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        else:
            raise HTTPException(status_code=400, detail=str(e))
            
@router.delete("/{room_id}")
async def delete_room(room_id: str, request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    room = RoomDatabase.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail=f"Room {room_id} not found")
    if room.get("creator_id") != user_id:
        raise HTTPException(status_code=403, detail="Only the room creator may delete this room")
    try:
        removed = RoomDatabase.delete_room(room_id)
        await emit_room_event("room:delete", {"room_id": room_id})
        return {"success": True, "message": f"Room {room_id} deleted.", "room": removed}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[rooms] delete_room failed for {room_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("/status")
async def update_room_status(req: UpdateRoomStatusRequest):
    try:
        room = RoomDatabase.update_room_status(req.room_id, req.status)
        await emit_room_event("room:update", room)
        return {
            "success": True,
            "room": room,
            "message": f"Room {req.room_id} status updated to '{req.status}'.",
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
