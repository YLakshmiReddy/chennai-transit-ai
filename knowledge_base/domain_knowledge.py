"""
domain_knowledge.py
-------------------
Static domain facts and configuration constants for the Chennai public
transit route recommendation system.

These values encode expert knowledge about the Chennai transit network and
are used by the constraint engine and route evaluator to make decisions.
"""

# ---------------------------------------------------------------------------
# Temporal knowledge
# ---------------------------------------------------------------------------

PEAK_HOURS = [(8, 10), (17, 20)]
"""
Peak congestion windows as (start_hour, end_hour) pairs (24-hour clock,
end exclusive).  Covers morning rush (8–10 AM) and evening rush (5–8 PM).
"""

# ---------------------------------------------------------------------------
# Mode / agency taxonomy
# ---------------------------------------------------------------------------

MODE_PRIORITY = {
    "Metro": 1,          # Fastest, most reliable
    "ExpressBus": 2,     # Express MTC / inter-city coaches
    "SuburbanRail": 2,   # Southern Railway commuter trains
    "LocalBus": 3,       # Ordinary MTC city buses
}
"""
Preference ranking for transit modes (1 = most preferred).
Used by the route ranker when priority_mode == "comfortable".
"""

AGENCY_MODE_MAP = {
    "CMRL": "Metro",
    "MTC": "LocalBus",
    "69": "LocalBus",    # MTC alternate agency_id used in some GTFS feeds
    "SR": "SuburbanRail",
}
"""
Maps GTFS agency_id values to their canonical mode names.
"""

# ---------------------------------------------------------------------------
# Visual / cartographic constants
# ---------------------------------------------------------------------------

MODE_COLORS = {
    "Metro": "#E63946",
    "LocalBus": "#457B9D",
    "ExpressBus": "#2A9D8F",
    "SuburbanRail": "#E9C46A",
}
"""
Hex colour codes for rendering each mode on a Folium map polyline.
"""

# ---------------------------------------------------------------------------
# Transfer and walking constraints
# ---------------------------------------------------------------------------

TRANSFER_BUFFER_MINS = 5
"""
Minimum number of minutes required between the arrival of one leg and the
departure of the next at a transfer stop.  Legs with a gap smaller than
this are considered infeasible under normal operating conditions.
"""

MAX_WALK_METERS = 500
"""
Maximum acceptable walking distance (metres) between any two consecutive
stops in a route.  Legs requiring more walking than this are penalised or
excluded.
"""
