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
from typing import List
import uuid
from .database import RoomDatabase

router = APIRouter(prefix="/api/rooms", tags=["rooms"])

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
  try:
    room_id = str(uuid.uuid4())[:8]
    room = RoomDatabase.create_room(
      room_id =  room_id,
      creator_id =  req.user_id,
      destination = req.destination,
      start_coord = req.start_coord,
      dest_coord =  req.dest_coord,
      max_members = req.max_members
    )
    return {
      "success": True, 
      "room": room, 
      "message":  f"Room {room_id} created."
    }
  except ValueError as e:
    raise HTTPException(status_code=400, detail=str(e))

@router.get("/list")
def list_rooms():
  rooms = RoomDatabase.get_active_rooms()
  return {"success": True, "rooms": rooms}

@router.post("/join")
def join_room(req: JoinRoomRequest):
  try: 
    room = RoomDatabase.join_room(req.room_id, req.user_id)

    return {
      "success": True,
      "room": room,
      "message": f"User {req.user_id} joined room {req.room_id}."
    }
  except ValueError as e:
    if "not found" in str(e):
      raise HTTPException(status_code=404, detail=str(e))
    else:
      raise HTTPException(status_code=400, detail=str(e))

@router.post("/leave")
def leave_room(req: LeaveRoomRequest):
  try:
    room = RoomDatabase.leave_room(req.room_id, req.user_id)
  
    return {
      "success": True,
      "room": room,
      "message": f"User {req.user_id} left room {req.room_id}."
    }
  except ValueError as e:
    if "not found" in str(e):
      raise HTTPException(status_code=404, detail=str(e))
    else:
      raise HTTPException(status_code=400, detail=str(e))

@router.put("/status")
def update_room_status(req: UpdateRoomStatusRequest):
  try:
    room = RoomDatabase.update_room_status(req.room_id, req.status)

    return {
      "success": True,
      "room": room,
      "message": f"Room {req.room_id} status updated to '{req.status}'."
    }
  except ValueError as e:
    raise HTTPException(status_code=404, detail=str(e))
