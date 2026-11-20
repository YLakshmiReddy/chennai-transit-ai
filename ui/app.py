"""
ui/app.py  —  Chennai Intelligent Transit Route Recommender
High-performance Streamlit application with spatial A* routing, persistent state,
one-click preset corridors, and rich interactive visual analytics.
"""

import os, sys, datetime, traceback, json, sqlite3
import streamlit as st

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

st.set_page_config(
    page_title="Chennai Transit AI",
    page_icon="🚇",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"About": "Chennai Intelligent Transit Route Recommender — Constraint-Based Reasoning Capstone"}
)

try:
    from streamlit_folium import st_folium
    _HAS_FOLIUM = True
except ImportError:
    _HAS_FOLIUM = False

from ui.components import render_route_card, build_route_map

DB_PATH = os.path.join(_ROOT, "data", "chennai_transit.db")
CHENNAI_CENTER = (13.08, 80.27)
PRIORITY_OPTIONS = ["Fastest ⚡", "Cheapest 💰", "Most Comfortable 🛋️", "Balanced ⚖️"]
PRIORITY_MAP = {
    "Fastest ⚡": "fastest",
    "Cheapest 💰": "cheapest",
    "Most Comfortable 🛋️": "comfortable",
    "Balanced ⚖️": "balanced",
}

PRESET_ROUTES = [
    {"label": "✈️ Central → Airport", "from": "Central", "to": "Airport", "from_hint": "M.G.R.Central", "to_hint": "AIRPORT"},
    {"label": "🛍️ T.Nagar → Koyambedu", "from": "T.Nagar", "to": "Koyambedu", "from_hint": "Thiyagarayanagar", "to_hint": "Koyambedu"},
    {"label": "🚆 Guindy → Tambaram", "from": "Guindy", "to": "Tambaram", "from_hint": "Guindy", "to_hint": "Tambaram"},
    {"label": "🏖️ Marina → Central", "from": "Anna Square", "to": "Central", "from_hint": "Anna Square", "to_hint": "M.G.R.Central"},
]


# ── Cached resources ──────────────────────────────────────────────────────────
@st.cache_resource(show_spinner="⚡ Loading optimized transit network cache (< 1s)…")
def load_graph():
    from engine.graph_builder import TransitGraphBuilder
    builder = TransitGraphBuilder(DB_PATH)
    graph = builder.build_graph(force_rebuild=False)
    return graph, builder

@st.cache_data(ttl=3600)
def get_db_stats():
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        stats = {}
        for t in ["stops", "routes", "trips", "stop_times", "fare_attributes", "transfers"]:
            c.execute(f"SELECT COUNT(*) FROM {t}")
            stats[t] = c.fetchone()[0]
        c.execute("SELECT agency_name FROM agencies")
        stats["agencies"] = [r[0] for r in c.fetchall()]
        conn.close()
        return stats
    except:
        return {}

@st.cache_data(ttl=600)
def search_stops_cached(query: str):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("PRAGMA table_info(stops)")
        cols = {r[1] for r in c.fetchall()}
        wc_expr = "wheelchair_accessible" if "wheelchair_accessible" in cols else "0"
        c.execute(f"""
            SELECT stop_id, stop_name, stop_lat, stop_lon, {wc_expr} AS wc
            FROM stops
            WHERE LOWER(stop_name) LIKE ?
            LIMIT 30
        """, (f"%{query.lower()}%",))
        rows = [dict(r) for r in c.fetchall()]
        conn.close()
        return rows
    except:
        return []

@st.cache_data(ttl=3600)
def get_popular_stops():
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            SELECT s.stop_name, s.stop_id, COUNT(*) as cnt
            FROM stop_times st JOIN stops s ON st.stop_id = s.stop_id
            GROUP BY st.stop_id ORDER BY cnt DESC LIMIT 20
        """)
        rows = [{"name": r[0], "id": r[1], "count": r[2]} for r in c.fetchall()]
        conn.close()
        return rows
    except:
        return []

@st.cache_data(ttl=3600)
def get_routes_by_agency():
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            SELECT a.agency_name, COUNT(r.route_id) as cnt
            FROM routes r JOIN agencies a ON r.agency_id = a.agency_id
            GROUP BY a.agency_id
        """)
        rows = {r[0]: r[1] for r in c.fetchall()}
        conn.close()
        return rows
    except:
        return {}


# ── CSS injection ─────────────────────────────────────────────────────────────
def inject_css():
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

* { box-sizing: border-box; }
html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }

#MainMenu, footer, header { visibility: hidden; }
.block-container { padding-top: 1rem !important; padding-bottom: 1rem !important; }

/* ── Hero banner ── */
.hero-banner {
    background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
    color: white; border-radius: 16px; padding: 24px 32px 20px;
    margin-bottom: 20px; position: relative; overflow: hidden;
    box-shadow: 0 8px 32px rgba(0,0,0,0.3);
}
.hero-title { font-size: 1.85rem; font-weight: 800; margin: 0; letter-spacing: -0.5px;
    background: linear-gradient(90deg, #fff, #a5b4fc); -webkit-background-clip: text;
    -webkit-text-fill-color: transparent; }
.hero-sub { margin: 6px 0 0; opacity: 0.8; font-size: 0.88rem; font-weight: 400; }
.hero-badges { margin-top: 12px; display: flex; gap: 8px; flex-wrap: wrap; }
.hero-badge {
    background: rgba(255,255,255,0.12); border: 1px solid rgba(255,255,255,0.2);
    color: white; padding: 4px 12px; border-radius: 20px; font-size: 0.75rem;
    font-weight: 600;
}

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1e1b4b 0%, #312e81 100%) !important;
    border-right: none !important;
}
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] span:not(.chip):not([data-baseweb="tag"]) {
    color: #e0e7ff;
}

/* Solid Black Letters in All Inputs on Clean White Background */
section[data-testid="stSidebar"] input,
section[data-testid="stSidebar"] input[type="text"],
section[data-testid="stSidebar"] input[type="number"],
section[data-testid="stSidebar"] .stTextInput input,
section[data-testid="stSidebar"] .stNumberInput input,
section[data-testid="stSidebar"] .stTimeInput input,
section[data-testid="stSidebar"] div[data-baseweb="input"] input,
section[data-testid="stSidebar"] div[data-baseweb="base-input"] input {
    background-color: #ffffff !important;
    color: #000000 !important;
    -webkit-text-fill-color: #000000 !important;
    caret-color: #000000 !important;
    font-weight: 700 !important;
    font-size: 0.95rem !important;
    border-radius: 8px !important;
    border: 1.5px solid #cbd5e1 !important;
    padding: 8px 12px !important;
}

section[data-testid="stSidebar"] div[data-baseweb="input"],
section[data-testid="stSidebar"] div[data-baseweb="base-input"] {
    background-color: #ffffff !important;
    border-radius: 8px !important;
    border: none !important;
}

section[data-testid="stSidebar"] input::placeholder {
    color: #64748b !important;
    -webkit-text-fill-color: #64748b !important;
    font-weight: 500 !important;
}

section[data-testid="stSidebar"] .stNumberInput button,
section[data-testid="stSidebar"] .stNumberInput button * {
    color: #1e1b4b !important;
    -webkit-text-fill-color: #1e1b4b !important;
}

section[data-testid="stSidebar"] div[data-baseweb="select"] *,
section[data-testid="stSidebar"] div[data-baseweb="select"] input {
    color: #000000 !important;
    -webkit-text-fill-color: #000000 !important;
    font-weight: 600 !important;
}

div[data-baseweb="popover"] *,
div[data-baseweb="menu"] * {
    color: #000000 !important;
    -webkit-text-fill-color: #000000 !important;
}

/* Preset buttons in sidebar */
.preset-btn-container { display: flex; flex-direction: column; gap: 6px; margin: 8px 0 16px; }

/* Timeline styling */
.timeline { position: relative; padding-left: 24px; margin: 16px 0; }
.timeline::before {
    content: ''; position: absolute; left: 10px; top: 0; bottom: 0;
    width: 2px; background: linear-gradient(180deg, #6366f1, #8b5cf6, #ec4899);
}
.timeline-stop {
    position: relative; margin-bottom: 16px;
    background: white; border-radius: 10px;
    padding: 10px 14px; border: 1px solid #f1f5f9;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}
.timeline-stop::before {
    content: ''; position: absolute; left: -20px; top: 50%;
    transform: translateY(-50%); width: 12px; height: 12px;
    border-radius: 50%; border: 2px solid;
}
.timeline-stop.origin::before   { background: #22c55e; border-color: #16a34a; }
.timeline-stop.dest::before     { background: #ef4444; border-color: #dc2626; }
.timeline-stop.transfer::before { background: #f59e0b; border-color: #d97706; }
.timeline-stop.leg::before      { background: #6366f1; border-color: #4f46e5; }

/* Reasoning log steps */
.reasoning-step {
    display: flex; gap: 10px; align-items: flex-start;
    padding: 8px 12px; border-radius: 8px; margin-bottom: 6px;
    font-size: 0.82rem;
}
.reasoning-step.pass { background: #f0fdf4; border-left: 3px solid #22c55e; }
.reasoning-step.fail { background: #fef2f2; border-left: 3px solid #ef4444; }
.reasoning-step.warn { background: #fffbeb; border-left: 3px solid #f59e0b; }
.reasoning-step.info { background: #eff6ff; border-left: 3px solid #3b82f6; }

/* Comparison table */
.compare-table { width: 100%; border-collapse: collapse; border-radius: 12px; overflow: hidden; margin-bottom: 16px; }
.compare-table th { background: #1e1b4b; color: white; padding: 10px 14px; font-size: 0.8rem; text-align: left; }
.compare-table td { padding: 10px 14px; font-size: 0.85rem; border-bottom: 1px solid #f3f4f6; }
.compare-table tr:hover td { background: #f8f7ff; }
.compare-table .best { color: #16a34a; font-weight: 700; }

.app-footer {
    background: #1e1b4b; color: #a5b4fc; border-radius: 12px;
    padding: 14px 24px; margin-top: 24px; display: flex;
    justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;
    font-size: 0.78rem;
}
</style>
""", unsafe_allow_html=True)


# ── Live clock JS ─────────────────────────────────────────────────────────────
def inject_clock():
    st.markdown("""
<div id="live-clock" style="font-size:1.1rem; font-weight:700; color:#a5b4fc; font-variant-numeric:tabular-nums;">🕐 --:--:--</div>
<script>
(function() {
    function updateClock() {
        var now = new Date();
        var h = String(now.getHours()).padStart(2,'0');
        var m = String(now.getMinutes()).padStart(2,'0');
        var s = String(now.getSeconds()).padStart(2,'0');
        var el = document.getElementById('live-clock');
        if (el) el.textContent = '🕐 ' + h + ':' + m + ':' + s;
    }
    updateClock();
    setInterval(updateClock, 1000);
})();
</script>
""", unsafe_allow_html=True)


# ── Stop Resolver ─────────────────────────────────────────────────────────────
def resolve_stop(label: str, text_input: str, builder) -> tuple:
    if not text_input.strip():
        return None, None
    matches = builder.get_stop_by_name(text_input.strip())
    if not matches:
        st.sidebar.warning(f"❌ No transit stops match '{text_input}'. Try a shorter name.")
        return None, None

    if len(matches) == 1:
        return matches[0]["stop_id"], matches[0]["stop_name"]

    options = {}
    for s in matches[:15]:
        agency_icon = "🚇" if s.get("agency") == "Metro" else ("🚆" if s.get("agency") == "Rail" else "🚌")
        wc_icon = " ♿" if s.get("wheelchair_accessible") else ""
        key = f"{agency_icon} {s['stop_name']} [{s.get('agency', 'Transit')}]{wc_icon} · ID: {s['stop_id']}"
        options[key] = s

    chosen_key = st.sidebar.selectbox(
        f"Select {label.capitalize()} Stop:",
        list(options.keys()),
        key=f"stop_select_{label}"
    )
    chosen = options[chosen_key]
    return chosen["stop_id"], chosen["stop_name"]


# ══════════════════════════════════════════════════════════════════════════════
# MAIN APPLICATION
# ══════════════════════════════════════════════════════════════════════════════
def main():
    inject_css()

    # Session state initialization
    if "routes" not in st.session_state:
        st.session_state["routes"] = None
    if "search_query" not in st.session_state:
        st.session_state["search_query"] = None
    if "from_text" not in st.session_state:
        st.session_state["from_text"] = "Central"
    if "to_text" not in st.session_state:
        st.session_state["to_text"] = "Airport"

    # Load graph & stats
    try:
        graph, builder = load_graph()
        graph_ok = True
    except Exception as exc:
        st.error(f"⚠️ Graph load failed: **{exc}**\n\n`data/chennai_transit.db` must exist.")
        graph_ok = False
        graph = builder = None

    db_stats = get_db_stats()
    popular = get_popular_stops()
    agency_routes = get_routes_by_agency()

    # ── HERO BANNER ───────────────────────────────────────────────────────────
    st.markdown(f"""
<div class="hero-banner">
  <div class="hero-title">🚇 Chennai Intelligent Transit Recommender</div>
  <div class="hero-sub">
    Constraint-Based Reasoning · CSP (AC-3) · Spatial A* Pathfinding · Real Multi-Modal GTFS
  </div>
  <div class="hero-badges">
    <span class="hero-badge">🏙️ Chennai Metropolitan Area</span>
    <span class="hero-badge">🚇 CMRL Metro</span>
    <span class="hero-badge">🚌 MTC Buses</span>
    <span class="hero-badge">🚆 Suburban Rail</span>
    <span class="hero-badge">📊 {db_stats.get('stops',0):,} Stops</span>
    <span class="hero-badge">🛣️ {db_stats.get('routes',0):,} Routes</span>
    <span class="hero-badge">⚡ Sub-Second Spatial A*</span>
  </div>
</div>
""", unsafe_allow_html=True)

    # ── SIDEBAR ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("""
<div style="text-align:center; padding: 6px 0 16px;">
  <div style="font-size:2.2rem;">🚇</div>
  <div style="font-size:1.15rem; font-weight:800; color:white;">Journey Planner</div>
  <div style="font-size:0.75rem; color:#a5b4fc; margin-top:2px;">Chennai Transit AI</div>
</div>""", unsafe_allow_html=True)

        inject_clock()

        # Preset Corridors
        st.markdown("<div style='margin-top:14px; font-size:0.75rem; font-weight:700; text-transform:uppercase; letter-spacing:1px; color:#a5b4fc;'>⚡ Popular Corridors (1-Click)</div>", unsafe_allow_html=True)
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            if st.button("✈️ Central → Airport", use_container_width=True):
                st.session_state["from_text"] = "Central"
                st.session_state["to_text"] = "Airport"
                st.rerun()
            if st.button("🚆 Guindy → Tambaram", use_container_width=True):
                st.session_state["from_text"] = "Guindy"
                st.session_state["to_text"] = "Tambaram"
                st.rerun()
        with col_p2:
            if st.button("🛍️ T.Nagar → Koyambedu", use_container_width=True):
                st.session_state["from_text"] = "Thiyagarayanagar"
                st.session_state["to_text"] = "Koyambedu"
                st.rerun()
            if st.button("🏖️ Marina → Central", use_container_width=True):
                st.session_state["from_text"] = "Anna Square"
                st.session_state["to_text"] = "Central"
                st.rerun()

        st.markdown("<div style='margin:14px 0 6px; font-size:0.75rem; font-weight:700; text-transform:uppercase; letter-spacing:1px; color:#a5b4fc;'>📍 Route Entry</div>", unsafe_allow_html=True)
        origin_input = st.text_input("Origin", value=st.session_state["from_text"], key="from_input_key")
        st.session_state["from_text"] = origin_input

        st.markdown("<div style='text-align:center; color:#a5b4fc; font-size:1.1rem; margin:2px 0;'>↕️</div>", unsafe_allow_html=True)
        dest_input = st.text_input("Destination", value=st.session_state["to_text"], key="to_input_key")
        st.session_state["to_text"] = dest_input

        # Resolve stops
        origin_id = origin_name = dest_id = dest_name = None
        if graph_ok and builder:
            origin_id, origin_name = resolve_stop("origin", origin_input, builder)
            dest_id, dest_name = resolve_stop("destination", dest_input, builder)

        st.markdown("<div style='margin:14px 0 6px; font-size:0.75rem; font-weight:700; text-transform:uppercase; letter-spacing:1px; color:#a5b4fc;'>⚙️ Constraints & Preferences</div>", unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            dep_time = st.time_input("🕐 Depart", value=datetime.time(8, 0))
        with col2:
            max_budget = st.number_input("💰 Budget (₹)", min_value=10, max_value=2000, value=200, step=10)

        max_transfers = st.slider("🔄 Max Transfers", 0, 5, 3)

        col3, col4 = st.columns(2)
        with col3:
            wheelchair = st.toggle("♿ Wheelchair", value=False)
        with col4:
            avoid_peak = st.toggle("🕗 Avoid Peak", value=False)

        st.markdown("<div style='margin:14px 0 6px; font-size:0.75rem; font-weight:700; text-transform:uppercase; letter-spacing:1px; color:#a5b4fc;'>🎯 Priority Mode</div>", unsafe_allow_html=True)
        priority_mode = st.radio("Priority", PRIORITY_OPTIONS, index=3, label_visibility="collapsed")

        st.markdown("<div style='margin:14px 0 6px; font-size:0.75rem; font-weight:700; text-transform:uppercase; letter-spacing:1px; color:#a5b4fc;'>🚌 Transit Modes</div>", unsafe_allow_html=True)
        col5, col6, col7 = st.columns(3)
        with col5: allow_metro = st.checkbox("Metro", value=True)
        with col6: allow_bus = st.checkbox("Bus", value=True)
        with col7: allow_rail = st.checkbox("Rail", value=True)

        st.markdown("<div style='margin-top:16px'></div>", unsafe_allow_html=True)
        search_clicked = st.button("🔍  Find Best Routes", use_container_width=True, type="primary", disabled=not graph_ok)

        # Footer stats in sidebar
        st.markdown("<div style='margin-top:20px; border-top: 1px solid rgba(255,255,255,0.1); padding-top:12px;'></div>", unsafe_allow_html=True)
        st.markdown(f"""
<div style='font-size:0.72rem; color:#818cf8; line-height:1.7;'>
  {'✅ Network Online (Cached)' if graph_ok else '❌ Offline'}<br/>
  📊 {graph.number_of_nodes():,} Stations · {graph.number_of_edges():,} Links<br/>
  ⚡ Multi-Modal Transfers Active
</div>
""" if graph_ok and graph else "", unsafe_allow_html=True)

    # ── Execute Search ────────────────────────────────────────────────────────
    if search_clicked:
        if not origin_id or not dest_id:
            st.error("⚠️ Please select valid origin and destination stops from the sidebar dropdowns.")
        elif origin_id == dest_id:
            st.error("⚠️ Origin and destination must be different stations.")
        else:
            dep_str = dep_time.strftime("%H:%M")
            user_prefs = {
                "wheelchair_required": wheelchair,
                "max_budget": float(max_budget),
                "max_transfers": max_transfers,
                "priority_mode": PRIORITY_MAP[priority_mode],
                "avoid_peak": avoid_peak,
                "allow_metro": allow_metro,
                "allow_bus": allow_bus,
                "allow_rail": allow_rail,
            }
            with st.spinner(f"🔍 Searching routes from {origin_name} to {dest_name}…"):
                from engine.router import ConstrainedRouter
                router = ConstrainedRouter(graph, DB_PATH)
                routes = router.find_routes(origin_id, dest_id, dep_str, user_prefs)

            st.session_state["routes"] = routes
            st.session_state["search_query"] = {
                "origin_name": origin_name,
                "dest_name": dest_name,
                "dep_str": dep_str,
                "user_prefs": user_prefs,
                "priority_mode": priority_mode,
            }

    # ── TABS ──────────────────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs(["🗺️ Route Planner", "📊 Network Explorer", "🧠 CSP Engine", "ℹ️ About"])

    # ════════════════════════════════════════════════════════════════
    # TAB 1: ROUTE PLANNER
    # ════════════════════════════════════════════════════════════════
    with tab1:
        routes = st.session_state["routes"]
        query = st.session_state["search_query"]

        col_map, col_results = st.columns([3, 2], gap="medium")

        # MAP COLUMN
        with col_map:
            st.markdown("#### 🗺️ Interactive Transit Map")
            display_routes = routes if routes else []
            route_map = build_route_map(display_routes, center=CHENNAI_CENTER)
            if _HAS_FOLIUM:
                st_folium(route_map, width=None, height=530, returned_objects=[])

        # RESULTS COLUMN
        with col_results:
            st.markdown("#### 🧭 Recommended Itineraries")

            if routes is not None:
                if len(routes) == 0:
                    # Explanatory fallback
                    st.markdown(f"""
<div style="background:#fff7ed; border-radius:12px; padding:18px; border:2px dashed #fca5a5;">
  <div style="font-weight:800; font-size:1.05rem; color:#991b1b; margin-bottom:8px;">
    😕 No Routes Found Matching Constraints
  </div>
  <div style="font-size:0.85rem; color:#475569; line-height:1.7;">
    From <b>{query['origin_name']}</b> → <b>{query['dest_name']}</b> at {query['dep_str']}.<br/>
    <b>Why did this happen?</b><br/>
    • <b>Transfers:</b> The journey may require more than {query['user_prefs']['max_transfers']} transfers. Try increasing <b>Max Transfers to 3 or 4</b>.<br/>
    • <b>Wheelchair Filter:</b> If enabled, only accessible Metro stations are permitted.<br/>
    • <b>Mode Restrictions:</b> Ensure Metro, Bus, and Rail are all checked.
  </div>
</div>
""", unsafe_allow_html=True)
                else:
                    st.markdown(f"""
<div style="background:linear-gradient(135deg,#eff6ff,#f0fdf4); border-radius:12px;
     padding:12px 16px; margin-bottom:14px; border:1px solid #bfdbfe;">
  <div style="font-weight:800; font-size:0.95rem; color:#1e40af;">
    ✅ Found {len(routes)} Pareto-Optimal Route{'s' if len(routes)>1 else ''}
  </div>
  <div style="font-size:0.83rem; color:#374151; margin-top:3px;">
    <b>{query['origin_name']}</b> → <b>{query['dest_name']}</b> · Depart {query['dep_str']}
  </div>
</div>""", unsafe_allow_html=True)

                    # Comparison table
                    with st.expander("📋 Side-by-Side Comparison", expanded=True):
                        _render_comparison_table(routes)

                    # Route cards
                    for idx, route in enumerate(routes, 1):
                        render_route_card(route, idx, query["priority_mode"])

            else:
                # Default empty state
                st.markdown("""
<div style="background:#f8fafc; border-radius:12px; padding:20px; border:1px solid #e2e8f0;">
  <div style="font-weight:700; color:#1e293b; margin-bottom:10px; font-size:1rem;">💡 Quick Start Guide</div>
  <div style="font-size:0.85rem; color:#475569; line-height:1.8;">
    1. Click any <b>1-Click Popular Corridor</b> in the sidebar (e.g. <i>✈️ Central → Airport</i>)<br/>
    2. Or type any station in <b>From</b> and <b>To</b><br/>
    3. Adjust your budget, departure time, and transfers<br/>
    4. Click <b>Find Best Routes</b> for sub-second Pareto recommendations!
  </div>
</div>
<div style="margin-top:16px;">
  <div style="font-size:0.75rem; font-weight:700; color:#64748b; letter-spacing:1px; margin-bottom:8px;">HIGH FREQUENCY STATIONS</div>
  <div style="display:flex; flex-wrap:wrap; gap:6px;">
    <span style="background:#e0e7ff; color:#3730a3; padding:4px 10px; border-radius:12px; font-size:0.75rem; font-weight:600;">Central Metro 🚇</span>
    <span style="background:#dcfce7; color:#166534; padding:4px 10px; border-radius:12px; font-size:0.75rem; font-weight:600;">Airport Metro ✈️</span>
    <span style="background:#fef3c7; color:#92400e; padding:4px 10px; border-radius:12px; font-size:0.75rem; font-weight:600;">Guindy Station 🚆</span>
    <span style="background:#f3e8ff; color:#6b21a8; padding:4px 10px; border-radius:12px; font-size:0.75rem; font-weight:600;">Koyambedu Bus 🚌</span>
    <span style="background:#ffe4e6; color:#9f1239; padding:4px 10px; border-radius:12px; font-size:0.75rem; font-weight:600;">Tambaram Terminal 🚏</span>
  </div>
</div>
""", unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════════
    # TAB 2: NETWORK EXPLORER
    # ════════════════════════════════════════════════════════════════
    with tab2:
        st.markdown("#### 📊 Chennai Transit Network Statistics")
        stat_cards = [
            ("#6366f1", db_stats.get('stops', 0), "Total Stations", "🚏"),
            ("#22c55e", db_stats.get('routes', 0), "Transit Routes", "🛣️"),
            ("#f59e0b", db_stats.get('trips', 0), "Daily Trips", "🗓️"),
            ("#ef4444", db_stats.get('stop_times', 0), "Scheduled Stops", "⏰"),
            ("#8b5cf6", graph.number_of_edges() if graph else 0, "Network Connections", "🔗"),
            ("#06b6d4", len(db_stats.get('agencies', [])), "Agencies", "🏢"),
        ]
        cols = st.columns(len(stat_cards))
        for col, (color, val, label, icon) in zip(cols, stat_cards):
            with col:
                st.markdown(f"""
<div style="background:white; border-radius:12px; padding:14px 16px; border-left:4px solid {color}; box-shadow:0 1px 6px rgba(0,0,0,0.06);">
  <div style="font-size:1.3rem;">{icon}</div>
  <div style="font-size:1.4rem; font-weight:800; color:#1e1b4b; margin-top:2px;">{val:,}</div>
  <div style="font-size:0.72rem; color:#64748b; font-weight:600;">{label}</div>
</div>""", unsafe_allow_html=True)

        st.markdown("<div style='margin:18px 0'></div>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("##### 🏢 Routes by Agency")
            for agency, count in agency_routes.items():
                pct = count / max(db_stats.get('routes', 1), 1) * 100
                color = "#E63946" if "Metro" in agency or "CMRL" in agency else \
                        "#E9C46A" if "Railway" in agency or "SR" in agency else "#457B9D"
                st.markdown(f"""
<div style="margin-bottom:10px;">
  <div style="display:flex; justify-content:space-between; font-size:0.85rem; margin-bottom:4px;">
    <span style="font-weight:600;">{agency}</span>
    <span style="color:#6b7280;">{count:,} routes ({pct:.1f}%)</span>
  </div>
  <div style="background:#f3f4f6; border-radius:6px; height:10px; overflow:hidden;">
    <div style="background:{color}; height:100%; width:{pct:.1f}%; border-radius:6px;"></div>
  </div>
</div>""", unsafe_allow_html=True)

        with c2:
            st.markdown("##### 🚏 Highest Frequency Stops")
            if popular:
                max_count = popular[0]["count"] if popular else 1
                for stop in popular[:8]:
                    pct = stop["count"] / max_count * 100
                    st.markdown(f"""
<div style="margin-bottom:8px;">
  <div style="display:flex; justify-content:space-between; font-size:0.82rem; margin-bottom:3px;">
    <span style="font-weight:600; color:#1e1b4b;">{stop['name'][:30]}</span>
    <span style="color:#6b7280; font-size:0.75rem;">{stop['count']:,}</span>
  </div>
  <div style="background:#f3f4f6; border-radius:6px; height:8px;">
    <div style="background:linear-gradient(90deg,#6366f1,#8b5cf6); height:100%; width:{pct:.1f}%; border-radius:6px;"></div>
  </div>
</div>""", unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════════
    # TAB 3: CSP ENGINE EXPLAINER
    # ════════════════════════════════════════════════════════════════
    with tab3:
        st.markdown("#### 🧠 Constraint Satisfaction Problem (CSP) Engine")
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("""
<div style="background:white; border-radius:14px; padding:18px; border-left:4px solid #ef4444; box-shadow:0 2px 8px rgba(0,0,0,0.06);">
  <div style="font-weight:800; font-size:1rem; margin-bottom:12px; color:#1e1b4b;">
    🔴 Hard Constraints
    <span style="font-size:0.72rem; color:#ef4444; margin-left:8px; font-weight:600;">STRICT ENFORCEMENT</span>
  </div>
  <div style="font-size:0.83rem; color:#374151; line-height:1.7;">
    <div style="margin-bottom:8px; padding:8px 10px; background:#fef2f2; border-radius:8px;">
      ♿ <b>Wheelchair Accessibility:</b> All stations on path must have accessible facilities.
    </div>
    <div style="margin-bottom:8px; padding:8px 10px; background:#fef2f2; border-radius:8px;">
      💰 <b>Budget Cap:</b> Cumulative journey fare must not exceed max budget.
    </div>
    <div style="margin-bottom:8px; padding:8px 10px; background:#fef2f2; border-radius:8px;">
      🔄 <b>Max Transfers:</b> Transfer limit strictly enforced.
    </div>
    <div style="padding:8px 10px; background:#fef2f2; border-radius:8px;">
      ⏱️ <b>Transfer Buffer ≥ 5 mins:</b> Enforces safe interchange time between connections.
    </div>
  </div>
</div>""", unsafe_allow_html=True)

        with col_b:
            st.markdown("""
<div style="background:white; border-radius:14px; padding:18px; border-left:4px solid #f59e0b; box-shadow:0 2px 8px rgba(0,0,0,0.06);">
  <div style="font-weight:800; font-size:1rem; margin-bottom:12px; color:#1e1b4b;">
    🟡 Soft Constraints
    <span style="font-size:0.72rem; color:#f59e0b; margin-left:8px; font-weight:600;">PENALTY OPTIMIZED</span>
  </div>
  <div style="font-size:0.83rem; color:#374151; line-height:1.7;">
    <div style="margin-bottom:8px; padding:8px 10px; background:#fffbeb; border-radius:8px;">
      🕗 <b>Peak Hour Penalty:</b> High road traffic during 8-10 AM and 5-8 PM adds penalty to buses, preferring Metro.
    </div>
    <div style="margin-bottom:8px; padding:8px 10px; background:#fffbeb; border-radius:8px;">
      🚌 <b>Mode Preference:</b> Metro/Rail prioritized over local buses for long-distance transit.
    </div>
    <div style="padding:8px 10px; background:#fffbeb; border-radius:8px;">
      🔄 <b>Transfer Minimization:</b> Each transfer adds a weighted cost based on priority mode.
    </div>
  </div>
</div>""", unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════════
    # TAB 4: ABOUT
    # ════════════════════════════════════════════════════════════════
    with tab4:
        st.markdown("""
#### ℹ️ Project Architecture & Domain Model

<div style="background:white; border-radius:14px; padding:20px; box-shadow:0 2px 10px rgba(0,0,0,0.06); line-height:1.8; font-size:0.88rem;">
  <b>🎓 Project Title:</b> Intelligent Public Transportation Route Recommendation Using Constraint-Based Reasoning<br/>
  <b>📚 Course:</b> DSA1606 — Knowledge Engineering | Capstone<br/>
  <b>🗄️ Dataset:</b> Chennai Unified GTFS (MTC Buses, CMRL Metro, Southern Railway Suburban Rail)<br/>
  <b>🧠 Solvers:</b> AC-3 Arc Consistency + Multi-Objective Spatial A* Pathfinding<br/>
  <b>⚡ Speed Optimization:</b> Pre-indexed binary disk cache (0.3s load time) + Spatial transfer links
</div>
""", unsafe_allow_html=True)

    # ── FOOTER ────────────────────────────────────────────────────────────────
    st.markdown(f"""
<div class="app-footer">
  <span>🚇 Chennai Transit AI · Knowledge Engineering Capstone</span>
  <span>Network: {'✅ Online (' + str(graph.number_of_nodes()) + ' stations)' if graph_ok and graph else '❌ Offline'}</span>
  <span>Algorithm: AC-3 · Spatial A* · Pareto</span>
  <span>Real GTFS Data</span>
</div>
""", unsafe_allow_html=True)


def _render_comparison_table(routes):
    headers = ["#", "Duration", "Fare ₹", "Transfers", "Transit Modes", "Rating"]
    min_time = min(r.get("total_time_mins", 9999) for r in routes)
    min_fare = min(r.get("total_fare", 9999) for r in routes)
    min_xfr = min(r.get("num_transfers", 9999) for r in routes)

    rows_html = ""
    for i, r in enumerate(routes, 1):
        t = r.get("total_time_mins", 0)
        f = r.get("total_fare", 0)
        x = r.get("num_transfers", 0)
        legs = r.get("legs", [])
        modes = list(dict.fromkeys(lg.get("mode", "?") for lg in legs if not lg.get("is_transfer")))
        mode_str = " + ".join(modes) if modes else "Walk"
        medal = ["🥇", "🥈", "🥉"][i - 1]
        t_cls = " class='best'" if t == min_time else ""
        f_cls = " class='best'" if f == min_fare else ""
        x_cls = " class='best'" if x == min_xfr else ""
        rows_html += f"""
<tr>
  <td><b>{medal} Route {i}</b></td>
  <td{t_cls}>{t} min</td>
  <td{f_cls}>₹{f:.0f}</td>
  <td{x_cls}>{x}</td>
  <td>{mode_str}</td>
  <td>{'⭐' * (4 - i)}</td>
</tr>"""

    st.markdown(f"""
<table class="compare-table">
  <thead><tr>{"".join(f"<th>{h}</th>" for h in headers)}</tr></thead>
  <tbody>{rows_html}</tbody>
</table>""", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
