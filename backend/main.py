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
CONTACT_EMAIL = "dang1532@mylaurier.ca"

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
    headers["From"] = CONTACT_EMAIL
    backoff = 0.5
    last_exc = None
    
    async with httpx.AsyncClient(timeout=15.0) as client:
        for attempt in range(1, 4):  # 3 attempts
            try:
                logger.info("Nominatim geocode attempt %d for %s", attempt, address)
                r = await client.get(url, params=params, headers=headers)
                logger.info("Nominatim status=%s for %s", r.status_code, address)
                if r.status_code != 200:
                    last_exc = Exception(f"Nominatim status {r.status_code}: {r.text[:200]}")
                    if 500 <= r.status_code < 600:
                        await asyncio.sleep(backoff * attempt)
                        continue
                    else:
                        break
                json_body = r.json()
                if not json_body:
                    last_exc = Exception("Nominatim returned no results")
                    break
                d = json_body[0]
                lat = float(d["lat"])
                lon = float(d["lon"])
                return [lat, lon]
            except (httpx.RequestError, httpx.HTTPStatusError, ValueError) as e:
                logger.exception("Nominatim attempt %d failed for %s: %s", attempt, address, e)
                last_exc = e
                await asyncio.sleep(backoff * attempt)
                continue

    # Nominatim failed so try photon
    try:
        photon_url = "https://photon.komoot.io/api/"
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(photon_url, params={"q": address, "limit": 1})
            logger.info("Photon status=%s for %s", r.status_code, address)
            if r.status_code == 200 and r.json().get("features"):
                feat = r.json()["features"][0]
                coords = feat["geometry"]["coordinates"]  # [lon, lat]
                return [float(coords[1]), float(coords[0])]
            else:
                logger.warning("Photon returned no results for %s: %s", address, r.text[:200])
    except Exception as e:
        logger.exception("Photon fallback failed for %s: %s", address, e)
        last_exc = e

    # Nothing worked
    raise ValueError(f"Geocoding failed for '{address}': {last_exc}")


async def osrm_route(from_coord, to_coord, mode="foot"): #osrm
    coords = f"{from_coord[1]},{from_coord[0]};{to_coord[1]},{to_coord[0]}"
    params = {"overview": "full", "geometries": "geojson", "steps": "true"}

    # Primary + backup OSRM servers
    OSRM_URLS = [
        f"https://router.project-osrm.org/route/v1/{mode}/{coords}",
        f"https://routing.openstreetmap.de/routed-car/route/v1/{mode}/{coords}",
        f"https://routing.openstreetmap.de/routed-foot/route/v1/{mode}/{coords}",
    ]

    last_error = None

    for url in OSRM_URLS:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.get(url, params=params)

            if r.status_code != 200:
                last_error = f"OSRM status {r.status_code} from {url}"
                continue

            data = r.json()
            if data.get("code") != "Ok":
                last_error = f"OSRM code {data.get('code')} from {url}"
                continue

            route = data["routes"][0]
            geometry = [[p[1], p[0]] for p in route["geometry"]["coordinates"]]

            return {
                "distance_m": route["distance"],
                "duration_s": route["duration"],
                "geometry": geometry
            }

        except Exception as e:
            last_error = str(e)
            continue

    raise ValueError(f"All OSRM servers failed: {last_error}")

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

