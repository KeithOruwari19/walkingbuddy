"""
database.py
Sinthujan Jayaranjan

This file handles the database for rooms and chat storage.
"""

from typing import List, Dict, Optional 
from datetime import datetime
import uuid

ROOMS_DB: Dict[str, Dict] = {}
CHAT_DB: Dict[str, List[Dict]] = {}

class RoomDatabase:
  @staticmethod
  def create_room(
    room_id: str,
    creator_id: str,
    destination: str,
    start_coord: List[float],
    dest_coord: List[float],
    max_members: int = 10
  ) -> Dict:
    if room_id in ROOMS_DB:
      raise ValueError(f"Room {room_id} already exists")

    room = {
      "room_id": room_id,
      "creator_id": creator_id,
      "destination": destination,
      "start_coord": start_coord,
      "dest_coord": dest_coord,
      "max_members": max_members,
      "members": [creator_id],
      "created_at": datetime.utcnow().isoformat(),
      "status": "active"
    }

    ROOMS_DB[room_id] = room
    CHAT_DB[room_id] = []
    return room

  @staticmethod
  def get_room(room_id: str) -> Optional[Dict]:
    return ROOMS_DB.get(room_id)

  @staticmethod
  def get_all_rooms() -> List[Dict]:
    return list(ROOMS_DB.values())

  @staticmethod
  def get_active_rooms() -> List[Dict]:
    return [room for room in ROOMS_DB.values() if room["status"] == "active"]

  @staticmethod
  def join_room(room_id: str, user_id: str) -> Dict:
    room = ROOMS_DB.get(room_id)

    if not room:
      raise ValueError(f"Room {room_id} not found")

    if user_id in room["members"]:
      raise ValueError(f"User {user_id} already in room")

    if len(room["members"]) >= room["max_members"]:
      raise ValueError(f"Room {room_id} is full")

    room["members"].append(user_id)
    return room

  @staticmethod
  def leave_room(room_id: str, user_id: str) -> Dict:
    room = ROOMS_DB.get(room_id)

    if not room:
      raise ValueError(f"Room {room_id} not found")

    if user_id not in room["members"]:
      raise ValueError(f"User {user_id} not found")
      
    room["members"].remove(user_id)

    if len(room["members"]) == 0:
      room["status"] = "complete"
    
    return room

  @staticmethod
  def update_room_status(room_id: str, status: str) -> Dict:
    room = ROOMS_DB.get(room_id)

    if not room:
      raise ValueError(f"Room {room_id} not found")

    room["status"] = status
    return room

class ChatDatabase:
  @staticmethod
  def add_message(room_id: str, user_id: str, message:  str) -> Dict:
    if room_id not in CHAT_DB:
      raise ValueError(f"Room {room_id} not found")

    msg = {
      "user_id": user_id,
      "message": message,
      "timestamp": datetime.utcnow().isoformat()
    }
    CHAT_DB[room_id].append(msg)
    return msg

  @staticmethod
  def get_messages(room_id: str, limit: Optional[int] = None) -> List[Dict]:
    messages = CHAT_DB.get(room_id, [])

    if limit:
      return messages[-limit:]
    return messages

  @staticmethod
  def clear_room_chat(room_id: str) -> bool:
    if room_id in CHAT_DB:
      CHAT_DB[room_id] = []
      return True
    return False
