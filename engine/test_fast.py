import os
import sqlite3
import math
import pickle
import time
import networkx as nx

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "chennai_transit.db")
CACHE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "transit_network.pickle")

def haversine_distance_m(lat1, lon1, lat2, lon2):
    """Distance in meters between two lat/lon coordinates."""
    R = 6371000  # meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def time_str_to_mins(t_str):
    if not t_str:
        return 0
    parts = t_str.strip().split(":")
    try:
        return int(parts[0]) * 60 + int(parts[1])
    except:
        return 0

print("Testing fast graph builder...")
t0 = time.time()
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# 1. Stops
c.execute("SELECT stop_id, stop_name, stop_lat, stop_lon, wheelchair_accessible FROM stops")
stops_data = c.fetchall()
G = nx.DiGraph()
stop_coords = {}
for sid, sname, lat, lon, wc in stops_data:
    lat, lon = float(lat or 0), float(lon or 0)
    G.add_node(
        str(sid),
        stop_name=sname or "",
        lat=lat,
        lon=lon,
        wheelchair_accessible=bool(wc),
        agency_id="CMRL" if str(sid).startswith("CMRL") else ("SR" if str(sid).startswith("SRR") else "MTC")
    )
    if lat and lon:
        stop_coords[str(sid)] = (lat, lon)

print(f"Loaded {len(G.nodes())} stops in {time.time()-t0:.2f}s")

# 2. Trip info (route_id, route_name, agency_id, mode)
c.execute("""
    SELECT t.trip_id, r.route_id, r.agency_id,
           COALESCE(r.route_short_name, r.route_long_name, r.route_id) as route_name
    FROM trips t JOIN routes r ON t.route_id = r.route_id
""")
trip_info = {}
for tid, rid, aid, rname in c.fetchall():
    aid_str = str(aid or "")
    if "CMRL" in aid_str or "Metro" in aid_str:
        mode = "Metro"
    elif "SR" in aid_str or "Rail" in aid_str:
        mode = "SuburbanRail"
    else:
        mode = "LocalBus"
    trip_info[str(tid)] = {"route_id": str(rid), "route_name": str(rname), "mode": mode, "agency_id": aid_str}

print(f"Loaded {len(trip_info)} trips info in {time.time()-t0:.2f}s")
conn.close()
