"""
chat_routes.py
Sinthujan Jayaranjan

This file handles all chat related operations which include:
- Sending messages within a room
- Retrieving message history
- Clearing chat history
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, List, Dict
from .database import ChatDatabase, RoomDatabase

from backend.auth import auth_storage

router = APIRouter(prefix="/api/chat", tags=["chat"])

class SendMessageRequest(BaseModel):
    room_id: str
    user_id: Optional[str] = None
    content: str  


@router.post("/send")
def send_message(req: SendMessageRequest):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
        
    room = RoomDatabase.get_room(req.room_id)
    if not room:
        raise HTTPException(status_code=404, detail=f"Room {req.room_id} not found")

    if req.user_id not in room.get("members", []):
        raise HTTPException(status_code=403, detail="User not in room")

    content = req.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    try:
        message_obj = ChatDatabase.add_message(
            req.room_id,
            req.user_id,
            content
        )

        try:
            user = auth_storage.get_user_by_id(user_id)
            if user:
                if isinstance(message_obj, dict):
                    message_obj["user_name"] = user.get("name")
                else:
                    message_obj = {"message": message_obj, "user_name": user.get("name")}
        except Exception:
            pass

        return {"success": True, "message": message_obj}

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{room_id}/messages")
def get_messages(room_id: str, limit: Optional[int] = 50):
    room = RoomDatabase.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail=f"Room {room_id} not found")

    messages = ChatDatabase.get_messages(room_id, limit)

    try:
        uids = set()
        for m in messages:
            uid = None
            if isinstance(m, dict):
                uid = m.get("user_id") or m.get("userId") or m.get("user")
            if uid:
                uids.add(str(uid))

        user_map: Dict[str, Optional[dict]] = {}
        for uid in uids:
            try:
                user_map[uid] = auth_storage.get_user_by_id(uid)
            except Exception:
                user_map[uid] = None

        for m in messages:
            if not isinstance(m, dict):
                continue
            uid = m.get("user_id") or m.get("userId") or m.get("user")
            if uid:
                u = user_map.get(str(uid))
                if u:
                    m["user_name"] = u.get("name")
    except Exception:
        pass

    return {
        "success": True,
        "room_id": room_id,
        "messages": messages 
    }


@router.delete("/{room_id}/messages")
def clear_messages(room_id: str, user_id: str):
    room = RoomDatabase.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail=f"Room {room_id} not found")

    if room["creator_id"] != user_id:
        raise HTTPException(status_code=403, detail="Only room creator can clear messages")

    ChatDatabase.clear_room_chat(room_id)

    return {
        "success": True,
        "message": f"All messages cleared for room {room_id}."
    }
