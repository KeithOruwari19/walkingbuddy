# Imports
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
import httpx
import math  # only for haversine
from typing import List, Optional
# Constants
app = FastAPI(title="WalkingBuddy Navigation + Rooms") 
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://bendang0309.github.io", "https://KeithOruwari19.github.io", "https://cp317-group-18-project.onrender.com"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
USER_AGENT = "CP317-Group-18-project (contact: dang1532@mylaurier.ca)"  # my email for nominatim

GEOCODE_CACHE: dict = {} # to store queries so that nominatim doesn't get repeat requests of the same content
GEOCODE_CACHE_LOCK = asyncio.Lock()

class RouteReq(BaseModel):
    start: str
    destination: str
    mode: str = "walking" 

# this is going to define the models for booking system on the Walking Buddy
class BookingRequest(BaseModel):
    user_id: str
    start_coord: List[float] # [lat, lon]
    destination_address: str # Send address and geocode on backend
    timestamp: str

async def geocode_nominatim(address: str):
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": address, "format": "json", "limit": 1}
    headers = {"User-Agent": USER_AGENT}
    async with httpx.AsyncClient(timeout=10.0) as client:
# honestly nominatim lookup should only take a couple hundred ms
# but I made timeout 5s cuz my internet is straight ASS so its just to make sure
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


@app.post("/service/v1/route")
async def get_route(req: RouteReq):
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

# Models start here

class RoomCreateReq(BaseModel):
    name: str = Field(..., min_length=1)
    host_user_id: str = Field(..., min_length=1)
    start_address: str = Field(..., min_length=1)         
    destination_address: str = Field(..., min_length=1)    
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

# notify room starts here

ROOM_DB: dict = {}
ROOM_DB_LOCK = asyncio.Lock()

ROOM_WS_CONNECTIONS: dict = {}
WS_LOCK = asyncio.Lock()

def now_iso() -> str:
    return datetime.utcnow().isoformat()

async def notify_room(room_id: str, message: dict):
    async with WS_LOCK:
        conns = set(ROOM_WS_CONNECTIONS.get(room_id, set()))
    dead = []
    for ws in conns:
        try:
            await ws.send_json(message)
        except Exception:
            dead.append(ws)
    if dead:
        async with WS_LOCK:
            for d in dead:
                ROOM_WS_CONNECTIONS.get(room_id, set()).discard(d)

@app.get("/service/v1/my_bookings")
async def get_bookings(user_id: str):
    # Checks if the frontend actually sent a user_id
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")

    # Creating a new list containing the bookings the user makes
    my_bookings = [b for b in BOOKINGS_DB if b["user_id"] == user_id]

    # Sorts the user booking from newest to oldest the key=lambda tells the sort function to look at the timestamp
    # Also the reverse=True just means that its sorted newest to oldest.
    my_bookings.sort(key=lambda b: b["timestamp"], reverse=True)
    # Should return a filtered and sorted list
    return my_bookings
