# Imports
import os
import asyncio
import logging
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Set, Any
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Query, Request, Response
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
import httpx
import math  # only for haversine

# fastapi
app = FastAPI(title="WalkingBuddy Navigation + Rooms") 
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://bendang0309.github.io", "https://KeithOruwari19.github.io", "https://cp317-group-18-project.onrender.com"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
USER_AGENT = "WalkingBuddy (contact: dang1532@mylaurier.ca)"  # my email for nominatim

SESSION_SECRET = os.getenv("SESSION_SECRET", "placeholder-session-secret") # placeholder so that website doesn't crash
SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "session")  
SESSION_COOKIE_SAMESITE = "lax"
SESSION_COOKIE_SECURE = os.getenv("ENV", "development") == "production"
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, session_cookie=SESSION_COOKIE_NAME)

# storages and locks
GEOCODE_CACHE: dict = {} # cache to reduce repeated nominatim lookups
GEOCODE_CACHE_LOCK = asyncio.Lock()

ROOM_DB: Dict[str, Dict[str, Any]] = {}
ROOM_DB_LOCK = asyncio.Lock()

ROOM_WS_CONNECTIONS: Dict[str, Set[WebSocket]] = {}
WS_LOCK = asyncio.Lock()

HISTORY_LIMIT = 200
MAX_MESSAGE_LEN = 2000

# models
class RouteReq(BaseModel):
    start: str
    destination: str
    mode: str = "walking" 

class RoomCreateReq(BaseModel):
    name: str = Field(..., min_length=1)
    host_user_id: str = Field(..., min_length=1)
    start: str = Field(..., min_length=1)         
    destination: str = Field(..., min_length=1)    
    capacity: int = Field(4, gt=0)
    private: bool = False 
    password: str | None = None # only if password is true
    mode: str = "walking"

class RoomInfo(BaseModel):
    id: str
    name: str
    host_user_id: str
    capacity: int
    private: bool
    participant_count: int
    participants: list
    start_address: str
    destination_address: str
    start_coord: list | None = None
    dest_coord: list | None = None
    created_at: str
    # navigation related starts here
    route_distance_m: float | None = None
    route_duration_s: float | None = None
    route_polyline: list | None = None
    route_steps: list | None = None
    route_source: str | None = None  # 'osrm' or 'haversine_fallback'
    route_error: str | None = None
    created_at: str

class JoinReq(BaseModel):
    user_id: str = Field(..., min_length=1)
    password: str | None = None # only checked if private = true

class LeaveReq(BaseModel):
    user_id: str = Field(..., min_length=1)
    
# helpers
def now_iso() -> str:
    return datetime.utcnow().isoformat()

def sanitize_text(s: str) -> str:
    return s[:MAX_MESSAGE_LEN]

def get_session_user(request: Request) -> Optional[str]:
    """
    Read the session cookie-managed session from request.session and return user_id.
    SessionMiddleware stores session data (signed) in the cookie. For HTTP routes this works.
    """
    # request.session is provided by SessionMiddleware for HTTP requests
    try:
        return request.session.get("user_id")
    except Exception:
        return None

# routing
async def geocode_nominatim(address: str):
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": address, "format": "json", "limit": 1}
    headers = {"User-Agent": USER_AGENT}
    async with httpx.AsyncClient(timeout=10.0) as client:
# honestly nominatim lookup should only take a couple hundred ms
# but I made timeout 10s just to make sure
        r = await client.get(url, params=params, headers=headers)
    r.raise_for_status()
    data = r.json()
    if not data:  # if the result is empty
        raise ValueError(f"Geocode failed: {address}")
    lat = float(data[0]["lat"])
    lon = float(data[0]["lon"])
    return lat, lon  # latitude, longitude as floats cuz osrm wants floats


async def osrm_route(from_coord, to_coord, mode="driving"):  # osrm api
    coords = f"{from_coord[1]},{from_coord[0]};{to_coord[1]},{to_coord[0]}"
    url = f"https://router.project-osrm.org/route/v1/{mode}/{coords}"
    params = {"overview": "full", "geometries": "geojson", "steps": "true"}
    # overview=full for full geometry
    # geometries=geojson returns coordinates as arrays
    # steps=true for instructions
    async with httpx.AsyncClient(timeout=20.0) as client:
        # route computation is more complex so I quadrupled the timeout to 20s
        r = await client.get(url, params=params)
    r.raise_for_status()
    j = r.json()
    if j.get("code") != "Ok" or not j.get("routes"):  # check if a route exists
        raise ValueError("OSRM route failed")
    rt = j["routes"][0]
    geometry = rt["geometry"]["coordinates"]  # list of [lon, lat]
    poly = [[lat, lon] for lon, lat in geometry]  # convert to [lat, lon] for leaflet (wip, might change frontend)
    distance_m = float(rt["distance"])
    duration_s = float(rt["duration"])
    legs = rt.get("legs", [])  # osrm splits a route into legs (segments) between waypoints
    steps = []
    if legs:  # check if its non-empty
        steps = legs[0].get("steps", [])
    return {"polyline": poly, "distance_m": distance_m, "duration_s": duration_s, "steps": steps}  # dict


# https://community.esri.com/t5/coordinate-reference-systems-blog/distance-on-a-sphere-the-haversine-formula/ba-p/902128
def haversine_km(a, b):  # just in case osrm fails
    # a,b = (lat,lon)
    R = 6371.0
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    hav = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * R * math.asin(math.sqrt(hav))


@app.post("/service/v1/walking_buddy")
async def create_room(req: RoomCreateReq, request: Request, response: Response):
    session_user = get_session_user(request)
    if not session_user:
        raise HTTPException(status_code=401, detail="authentication required (session cookie)")
    if session_user != req.host_user_id:
        raise HTTPException(status_code=403, detail="session user does not match host_user_id")

    # 1) geocode start and dest
    try:
        start_coord = await geocode_nominatim(req.start)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Start geocode failed: {e}")
    try:
        dest_coord = await geocode_nominatim(req.destination)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Destination geocode failed: {e}")

    # 2) OSRM
    try:
        res = await osrm_route(start_coord, dest_coord, mode=req.mode)
        return {
            "start": req.start,
            "destination": req.destination,
            "start_coord": start_coord,
            "dest_coord": dest_coord,
            "distance_m": res["distance_m"],
            "duration_s": res["duration_s"],
            "polyline": res["polyline"],
            "steps": res["steps"],
            "source": "osrm",
            "fallback": False
        }
    except Exception as e:
        # if osrm fails try haversine
        km = haversine_km(start_coord, dest_coord)
        return {
            "start": req.start,
            "destination": req.destination,
            "start_coord": start_coord,
            "dest_coord": dest_coord,
            "distance_m": round(km * 1000, 1),
            "duration_s": None,
            "polyline": [[start_coord[0], start_coord[1]], [dest_coord[0], dest_coord[1]]],
            "steps": [],
            "source": "haversine_fallback",
            "fallback": True,
            "error": str(e)
        }
    room_id = str(uuid.uuid4())
    created_at = now_iso()
    room_obj = {
        "id": room_id,
        "name": req.name,
        "host_user_id": req.host_user_id,
        "capacity": req.capacity,
        "private": bool(req.private),
        "password": req.password if req.private else None,
        "participants": [{"user_id": req.host_user_id, "joined_at": created_at}],  # host auto-joins
        "participant_count": 1,
        "start_address": req.start_address,
        "destination_address": req.destination_address,
        "start_coord": start_coord,
        "dest_coord": dest_coord,
        "created_at": created_at,
        **route_info,
    }

    # store room
    async with ROOM_DB_LOCK:
        ROOM_DB[room_id] = room_obj

    logger.info("Room created: %s host=%s name=%s", room_id, req.host_user_id, req.name)

    # notify websocket 
    await notify_room(room_id, {"type": "system", "text": f"Room created: {req.name}", "ts": created_at})

    return room_obj

