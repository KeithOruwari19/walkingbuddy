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
from typing import List, Dict, Optional
from datetime import datetime

router = APIRouter(prefix="/api/chat",  tags=["chat"])

CHAT_DB:Dict[str, List[Dict]] = {}

class SendMessageRequest(BaseModel):
  room_id: str
  user_id: str
  message:str

@router.post("/send")
def send_message(req: SendMessageRequest):
  if req.room_id not in CHAT_DB:
    CHAT_DB[req.room_id] = []
  message_obj = {
    "user_id": req.user_id,
    "message": req.message,
    "timestamp": datetime.utcnow().isoformat()
  }
  CHAT_DB[req.room_id ].append(message_obj)
  return {"success": True, "message": message_obj}

@router.get("/{room_id}/messages")
def get_messages(room_id: str, limit: int = 50):
  messages = CHAT_DB.get(room_id, [])
  return {"success": True, "room_id": room_id, "messages": messages[-limit:]}

@router.get("/{room_id}/messages")
def clear_messages(room_id: str, user_id: str):
  CHAT_DB[room_id] = []
  return {"success": True, "message": f"Messages for room {room_id} cleared."}
