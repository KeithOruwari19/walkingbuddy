"""
chat_routes.py
Sinthujan Jayaranjan

This file handles all chat related operations which include:
- Sending messages within a room
- Retrieving message history
- Clearing chat history
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from .database import ChatDatabase, RoomDatabase

router = APIRouter(prefix="/api/chat",  tags=["chat"])

class SendMessageRequest(BaseModel):
  room_id: str
  user_id: str
  message:str

@router.post("/send")
def send_message(req: SendMessageRequest):
  room = RoomDatabase.get_room(req.room_id)
  if not room:
    raise HTTPException(status_code=404, detail=f"Room {req.room_id} not found")

  if req.user_id not in room["members"]:
    raise HTTPException(status_code=403, detail="User not in room")

  try:
    message_obj = ChatDatabase.add_message(
      req.room_id,
      req.user_id,
      req.message
    )

    return {"success": True, "message": message_obj}

  except ValueError as e:
    raise HTTPException(status_code=404, detail=str(e))

@router.get("/{room_id}/messages")
def get_messages(room_id: str, limit: Optional[int] = 50):
  room = RoomDatabase.get_room(room_id)
  if not room:
    raise HTTPException(status_code=404, detail=f"Room {room_id} not found")

  messages = ChatDatabase.get_messages(room_id, limit)

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

  return{
    "success": True,
    "message": f"All messages cleared for room {room_id}."
  }
