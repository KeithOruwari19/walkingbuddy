"""
-------------------------------------------------------
[program description]
-------------------------------------------------------
Author:  Ben Dang
ID:      169071532
Email:   dang1532@mylaurier.ca
__updated__ = "2025-10-26"
-------------------------------------------------------
"""
# Imports
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import httpx
import math  # only for haversine
from typing import List, Optional
# Constants
app = FastAPI(title="Laurier Route Planner")  # name is wip
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://bendang0309.github.io", "https://KeithOruwari19.github.io", "https://cp317-group-18-project.onrender.com"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
USER_AGENT = "CP317-Group-18-project (contact: dang1532@mylaurier.ca)"  # my email for nominatim


class RouteReq(BaseModel):
    start: str
    destination: str
    mode: str = "walking"  # driving or walking

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

BOOKING_DB = [] # this is just to store temporarily like a database
MATCH_DISTANCE_KM = 1.0 # if two users start within 1.0 km of each other then that would be a match

@app.post("/service/v1/walking_buddy")
# I am not going to be creative with the name lol
async def book_walk_and_find_buddies(req: BookingRequest):

    # Grocoding the user's destination and its better to do it on the backend cuz we got the function for it here
    # Also its better to send less data from frontend
    try:
        dest_coord = await geocode_nominatim(req.destination_address)
    except Exception as e:
        # if the address is not an actual address this should fail
        raise HTTPException(status_code=400, detail=f"Destination geocode failed: {e}")

    # new booking object for defintions makes it easier for me to call
    new_booking = {
        "user_id": req.user_id,
        "start_coord": req.start_coord,
        "destination_address": req.destination_address, # Store the address string
        "dest_coord": dest_coord, # Store the geocoded coordinates
        "timestamp": req.timestamp
    }

    # This is supposed to find matches by looping through the temporary list as a database
    matches = []
    for booking in BOOKING_DB:
        # can't let the user match with themselves
        if booking["user_id"] == req.user_id:
            continue

        # uses the haversine function to find the distance between the user start and the other user start point.
        dist_km = haversine_km(req.start_coord, booking["start_coord"])

        # If the distance between them is between the 1 km then its a match.
        if dist_km <= MATCH_DISTANCE_KM:
            matches.append({
                "user_id": r["user_id"],
                "start_coord": r["start_coord"],
                "distance_km": dist_km
            })
    # Saves the new booking to the list
    BOOKING_DB.append(new_booking)

    #  Sends back both the confirmation of their booking and the list of matches that's found
    return {
        "booking": new_booking,
        "matches": { 
            "count": len(matches),
            "matches": matches
        }
    }

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
