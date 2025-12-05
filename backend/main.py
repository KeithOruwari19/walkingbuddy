"""
-------------------------------------------------------
main.py dictates the main backend logic for the program
-------------------------------------------------------
__updated__ = "2025-12-05"
-------------------------------------------------------
"""
# Imports
import os 
import uvicorn
import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
import logging
from fastapi.responses import PlainTextResponse # pinger

logger = logging.getLogger("uvicorn.error")

# Importing the modules
# Nauman
from backend.auth import auth_routes

# Sinthujan 
from backend.walkingbuddy import room_routes, chat_routes

logger.info("CORS allow_origins = %s", ["https://KeithOruwari19.github.io", "https://cp317-group-18-project.onrender.com"])
# fastapi
app = FastAPI(title="WalkingBuddy Navigation + Rooms") 
app.add_middleware(
    CORSMiddleware,
    # I know we had the code below as a placeholder but now we should have frontend to initialize this
    allow_origins=["https://keithoruwari19.github.io", "https://cp317-group-18-project.onrender.com"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Nauman's part should now work with backend
SESSION_SECRET = os.getenv("SESSION_SECRET", "placeholder-session-secret") # placeholder so that website doesn't crash
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, same_site="none", https_only=True)

 # Connecting all the modules via router
app.include_router(auth_routes.router)
app.include_router(room_routes.router)
app.include_router(chat_routes.router)
app.include_router(auth_routes.user_router)


USER_AGENT = "WalkingBuddy/1.0"

@app.on_event("startup")
async def _log_routes():
    logger.info("Registered routes: %s", [r.path for r in app.routes])

# pings render every 3 mins with Better Stack Uptime, because the free plan spins down with inactivity
@app.get("/ping", response_class=PlainTextResponse) 
async def ping():
    return "OK"

@app.get("/api/navigation/route")
async def get_route_data(start: str, destination: str, mode: str = "foot"):
    try:
        # getting coords for the start and dest
        start_coord = await geocode_nominatim(start)
        dest_coord = await geocode_nominatim(destination)
        # walking path data from osrm
        route_data = await osrm_route(start_coord, dest_coord, mode)
        return {"success": True, "start_coord": start_coord, "dest_coord": dest_coord, "route": route_data}

    except Exception as e:
        return {"success": False, "error": str(e)}

# routing
async def geocode_nominatim(address: str):
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": address, "format": "json", "limit": 1}
    headers = {"User-Agent": USER_AGENT}
    async with httpx.AsyncClient(timeout=60.0) as client:
# honestly nominatim lookup should only take a couple hundred ms
# but I made timeout 1m just to make sure
        r = await client.get(url, params=params, headers=headers)
    if not r.json():  # if the result is empty
        raise ValueError(f"Address is not found: {address}")
    data = r.json()[0]
    return [float(data["lat"]), float(data["lon"])] # latitude, longitude as floats cuz osrm wants floats


async def osrm_route(from_coord, to_coord, mode):  # osrm api
    coords = f"{from_coord[1]},{from_coord[0]};{to_coord[1]},{to_coord[0]}"
    url = f"https://router.project-osrm.org/route/v1/foot/{coords}"
    params = {"overview": "full", "geometries": "geojson", "steps": "true"}
    # overview=full for full geometry
    # geometries=geojson returns coordinates as arrays
    # steps=true for instructions
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.get(url, params=params)
    if r.status_code != 200:
        raise ValueError("OSRM route failed")
    data = r.json()
    if data["code"] != "Ok":
        raise ValueError("No route found")
    route = data["routes"][0]
    geometry = [[p[1], p[0]] for p in route["geometry"]["coordinates"]]
    return {"distance_m": route["distance"], "duration_s": route["duration"], "geometry": geometry} 

@app.get("/api/navigation/reverse")
async def reverse_geocode(lat: float, lon: float):
    try:
        url = "https://nominatim.openstreetmap.org/reverse"
        params = {
            "lat": lat,
            "lon": lon,
            "format": "json",
        }
        headers = {"User-Agent": USER_AGENT}

        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.get(url, params=params, headers=headers)

        data = r.json()

        address = data.get("display_name")
        if not address:
            raise ValueError("Address not found")

        return {"success": True, "address": address, "raw": data}

    except Exception as e:
        return {"success": False, "error": str(e)}

if __name__ =="__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

