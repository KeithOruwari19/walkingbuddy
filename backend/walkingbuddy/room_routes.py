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

import logging
logger = logging.getLogger(__name__)

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
    user_id: Optional[str] = None
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
    user_id: Optional[str] = None
    room_id: str

class LeaveRoomRequest(BaseModel):
    user_id: Optional[str] = None
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

def attach_canonical_ids(room: dict, prefer_room_id: Optional[str] = None) -> dict:
    if not isinstance(room, dict):
        return room
    rid = (
        room.get("room_id")
        or room.get("id")
        or room.get("uuid")
        or room.get("roomId")
        or prefer_room_id
    )
    if not rid:
        return room
    rid = str(rid)
    room["room_id"] = rid
    room["id"] = rid
    room["uuid"] = rid
    return room

async def emit_room_event(event_type: str, room: dict):
    attach_creator_name(room)
    attach_canonical_ids(room)
    payload = {
        "type": event_type,
        "room": room,
        "room_id": room.get("room_id"),
    }
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
        try:
            attach_creator_name(room)
        except Exception:
            logger.exception("[rooms.create] attach_creator_name failed for %s", room_id)
        try:
            await emit_room_event("room:new", room)
        except Exception:
            logger.exception("[rooms.create] emit_room_event failed for %s (broadcast error)", room_id)

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
    enriched = [attach_canonical_ids(attach_creator_name(dict(r))) for r in rooms]
    return {"success": True, "rooms": enriched}

@router.post("/join")
async def join_room(req: JoinRoomRequest, request: Request):
    # Prefer the session user id; fall back to the body or query param (useful for debugging).
    user_id = None
    try:
        user_id = request.session.get("user_id")
    except Exception:
        user_id = None

    # fallback to provided body or query param if no session (debugging mode)
    if not user_id:
        user_id = req.user_id or request.query_params.get("user_id")

    if not user_id:
        logger.info("[rooms.join] auth failed: no session and no user_id supplied (headers=%s)", dict(request.headers))
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        # Ensure we pass the resolved user_id to the DB call
        room = RoomDatabase.join_room(req.room_id, str(user_id))
        attach_creator_name(room)
        attach_canonical_ids(room)
        await emit_room_event("room:join", room)
        return {
            "success": True,
            "room": room,
            "message": f"User {user_id} joined room {req.room_id}.",
        }
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=str(e))
        else:
            raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("[rooms.join] unexpected error joining %s for user %s", req.room_id, user_id)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/leave")
async def leave_room(req: LeaveRoomRequest, request: Request):
    user_id = None
    try:
        user_id = request.session.get("user_id")
    except Exception:
        user_id = None

    if not user_id:
        user_id = req.user_id or request.query_params.get("user_id")

    if not user_id:
        logger.info("[rooms.leave] auth failed: no session and no user_id supplied (headers=%s)", dict(request.headers))
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        room = RoomDatabase.leave_room(req.room_id, str(user_id))
        attach_creator_name(room)
        attach_canonical_ids(room)
        await emit_room_event("room:leave", room)
        return {
            "success": True,
            "room": room,
            "message": f"User {user_id} left room {req.room_id}.",
        }
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=str(e))
        else:
            raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("[rooms.leave] unexpected error leaving %s for user %s", req.room_id, user_id)
        raise HTTPException(status_code=500, detail="Internal server error")
            
@router.delete("/{room_id}")
async def delete_room(room_id: str, request: Request, user_id: Optional[str] = None):
    session_user = None
    try:
        session_user = request.session.get("user_id") or request.session.get("id") or request.session.get("userId")
    except Exception:
        session_user = None

    logger.info("[rooms.delete] request to delete %s — session_user=%s query_user=%s headers=%s",
                room_id, session_user, user_id, dict(request.headers))

    auth_user = session_user or user_id or request.query_params.get("user_id")
    if not auth_user:
        try:
            logger.info("[rooms.delete] session keys: %s", list(request.session.keys()))
        except Exception:
            logger.info("[rooms.delete] could not enumerate session keys")
        raise HTTPException(status_code=401, detail="Authentication required (no session). For debugging you can pass ?user_id=<id>.")

    room = RoomDatabase.get_room(room_id)
    if not room:
        logger.info("[rooms.delete] room %s not found (auth_user=%s)", room_id, auth_user)
        raise HTTPException(status_code=404, detail=f"Room {room_id} not found")

    creator = room.get("creator_id") or room.get("creatorId") or room.get("creator") or room.get("user_id") or None

    logger.info("[rooms.delete] found room=%s creator=%s auth_user-provided=%s", room_id, creator, auth_user)

    def norm(v):
        try:
            return None if v is None else str(v)
        except Exception:
            return str(v)

    if norm(creator) != norm(auth_user):
        logger.info("[rooms.delete] permission denied — creator(%s) != auth(%s)", norm(creator), norm(auth_user))
        raise HTTPException(status_code=403, detail="Only the room creator may delete this room")

    try:
        removed = RoomDatabase.delete_room(room_id)
        await emit_room_event("room:delete", {"room_id": room_id})
        logger.info("[rooms.delete] deleted room %s by user %s", room_id, auth_user)
        return {"success": True, "message": f"Room {room_id} deleted.", "room": removed}
    except ValueError as e:
        logger.exception("[rooms.delete] delete_room ValueError for %s: %s", room_id, e)
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("[rooms.delete] unexpected error deleting %s: %s", room_id, e)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("/status")
async def update_room_status(req: UpdateRoomStatusRequest):
    try:
        room = RoomDatabase.update_room_status(req.room_id, req.status)
        attach_creator_name(room)
        attach_canonical_ids(room)
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
