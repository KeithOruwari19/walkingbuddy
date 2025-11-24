"""
Room Routes.py
Sinthujan Jayaranjan

This file handles all the room-related operations which include:
- Creating new walking rooms
- Listing available rooms
- Joining existing rooms
- Updating room status
"""

from fastapi import APIRouter, HTTPException
from  pydantic import BaseModel
from typing import List, Dict
import uuid

router = APIRouter(prefix="/api/rooms", tags=["rooms"])

ROOMS_DB: Dict[str, Dict] = {}

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

@router.post("/create")
def create_room(req: CreateRoomRequest):
  room_id = str(uuid.uuid4())[:8]
  room = {
    "room_id": room_id,
    "creator_id": req.user_id,
    "destination": req.destination,
    "start_coord": req.start_coord,
    "dest_coord": req.max_members,
    "members": [req.user_id],
    "status": "active"
  }
  ROOMS_DB[room_id] = room
  return {"success": True, "room": room, "message":  f"Room {room_id} created."}

@router.get("/list")
def list_rooms():
  rooms = [room for room in ROOMS_DB.values() if room["status"] == "active"]
  return {"success": True, "rooms": rooms}

@router.post("/join")
def join_room(req: JoinRoomRequest):
  rooms = ROOMS_DB.get(req.room_id)
  if not room:
    raise HTTPException(status_code=404, detail="Room does not exist.")
  if req.user_id in room["members"]:
    raise HTTPException(status_code=400, detail="User is already in room.")
  if len(room["members"]) >= room["max_members"]:
    raise HTTPException(status_code=400, detail="Room is full.")
  return {"success": True, "room": room, "message":  "User joined the room."}

@router.post("/leave")
def leave_room(req: LeaveRoomRequest):
  rooms = ROOMS_DB.get(req.room_id)
  if not room:
    raise HTTPException(status_code=404, detail="Room not found.")
  if req.user_id not in room["members"]:
    raise HTTPException(status_code=400, detail="User is not in room.")
  room["members"].remove(req.user_id)
  if len(room["members"]) == 0:
    room["status"] = "complete"
  return {"success": True, "room": room, "message":  "User left the room."}

@router.put("/status")
def update_room_status(req: UpdateRoomStatusRequest):
  room = ROOMS_DB.get(req.room_id)
  if not room:
    raise HTTPException(status_code=404, detail="Room not found.")
  room["status"] = req.status
  return {"success": True, "room": room, "message": f"Status set to {req.status}."}
  
