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
from typing import List, Optional
import uuid
import asyncio
import json
from backend.auth import auth_storage

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
    room_name: Optional[str] = None
    name: Optional[str] = None
    meet_time: Optional[str] = None
    meetTime: Optional[str] = None
    start_location: Optional[str] = None
    startLocation: Optional[str] = None

class JoinRoomRequest(BaseModel):
    user_id: str
    room_id: str

class LeaveRoomRequest(BaseModel):
    user_id: str
    room_id: str

class UpdateRoomStatusRequest(BaseModel):
    room_id: str
    status: str

def attach_creator_name(room: dict) -> dict:
    """
    Mutates (and returns) room dict to include 'creator_name' if possible.
    Uses auth_storage.get_user_by_id(...) which returns minimal public user info.
    """
    if not isinstance(room, dict):
        return room
    creator_id = room.get("creator_id") or room.get("creatorId") or room.get("creator") or room.get("user_id")
    if not creator_id:
        room["creator_name"] = room.get("creator_name") or None
        return room
    try:
        user = auth_storage.get_user_by_id(str(creator_id))
    except Exception:
        user = None
    if user:
        room["creator_name"] = user.get("name")
    else:
        room["creator_name"] = room.get("creator_name") or None
    return room

async def emit_room_event(event_type: str, room: dict):
    attach_creator_name(room)
    payload = {"type": event_type, "room": room}
    await manager.broadcast(payload)

@router.post("/create")
async def create_room(req: CreateRoomRequest, request: Request):
    try:
        room_id = str(uuid.uuid4())[:8]
        name = req.room_name or req.name
        meet = req.meet_time or getattr(req, "meetTime", None)
        start_loc = req.start_location or getattr(req, "startLocation", None)

        room = RoomDatabase.create_room(
            room_id=room_id,
            creator_id=req.user_id,
            destination=req.destination,
            start_coord=req.start_coord,
            dest_coord=req.dest_coord,
            max_members=req.max_members,
            name=name,
            meet_time=meet,
            start_location=start_loc
        )

        try:
            session_name = (request.session.get("user_name") or request.session.get("name") or None)
            if session_name:
                room["creator_name"] = session_name
        except Exception:
            pass

        attach_creator_name(room)

        await emit_room_event("room:new", room)
        return {"success": True, "room": room, "message": f"Room {room_id} created."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal server error")
        
@router.get("/list")
def list_rooms():
    rooms = RoomDatabase.get_active_rooms()
    enriched = [attach_creator_name(dict(r)) for r in rooms]
    return {"success": True, "rooms": enriched}

@router.post("/join")
async def join_room(req: JoinRoomRequest):
    try:
        room = RoomDatabase.join_room(req.room_id, req.user_id)
        attach_creator_name(room)
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
        attach_creator_name(room)
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
        attach_creator_name(room)
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
