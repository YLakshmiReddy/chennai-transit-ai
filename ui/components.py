"""
ui/components.py
Enhanced rendering components for the Chennai Transit Streamlit app.
Includes interactive Folium maps, detailed journey cards, visual reasoning logs,
and network analytics.
"""

import folium
from folium import plugins
import streamlit as st

# ── Mode styling ─────────────────────────────────────────────────────────────
MODE_COLORS = {
    "Metro": "#E63946",
    "LocalBus": "#457B9D",
    "ExpressBus": "#2A9D8F",
    "SuburbanRail": "#E9C46A",
    "Transfer": "#6c757d",
}

MODE_ICONS = {
    "Metro": "🚇",
    "LocalBus": "🚌",
    "ExpressBus": "🚍",
    "SuburbanRail": "🚆",
    "Transfer": "🚶",
}

PRIORITY_LABEL = {
    "Fastest": "⚡ Fastest",
    "Cheapest": "💰 Cheapest",
    "Most Comfortable": "🛋️ Most Comfortable",
    "Balanced": "⚖️ Balanced",
}


def _mode_badge(mode: str) -> str:
    """Return an HTML badge for a transit mode."""
    color = MODE_COLORS.get(mode, "#888888")
    icon = MODE_ICONS.get(mode, "🚐")
    return (
        f'<span style="background:{color}; color:white; padding:3px 10px; '
        f'border-radius:12px; font-size:0.75rem; margin-right:4px; font-weight:700; '
        f'box-shadow:0 1px 3px rgba(0,0,0,0.15); display:inline-flex; align-items:center; gap:4px;">'
        f'{icon} {mode}</span>'
    )


def render_route_card(route: dict, index: int, priority_mode: str = "Balanced") -> None:
    """
    Render a single route result card with rich metrics, timeline, and reasoning trace.
    """
    legs = route.get("legs", [])
    total_time = route.get("total_time_mins", 0)
    total_fare = route.get("total_fare", 0.0)
    transfers = route.get("num_transfers", 0)
    reasoning = route.get("reasoning_trace", [])

    # Approximate CO2 savings compared to driving (approx 120g CO2/km driving vs 30g transit)
    total_dist = sum(leg.get("distance_km", 0) or 2.5 for leg in legs)
    co2_saved = max(round(total_dist * 0.09, 2), 0.1)

    modes_used = list(dict.fromkeys(leg.get("mode", "?") for leg in legs if not leg.get("is_transfer")))
    badges_html = " ".join(_mode_badge(m) for m in modes_used)
    medal = ["🥇", "🥈", "🥉"][index - 1] if index <= 3 else f"#{index}"

    label = f"{medal} Route #{index} · {total_time} min · ₹{total_fare:.0f} · {transfers} transfer{'s' if transfers != 1 else ''}"

    with st.expander(label, expanded=(index == 1)):
        # Top metrics banner
        st.markdown(f"""
        <div style="background:#f8fafc; border-radius:12px; padding:12px 16px; margin-bottom:14px; border:1px solid #e2e8f0;">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
                <div>{badges_html}</div>
                <div style="font-size:0.75rem; color:#10b981; font-weight:700; background:#ecfdf5; padding:3px 10px; border-radius:12px; border:1px solid #a7f3d0;">
                    🌱 Saves ~{co2_saved} kg CO₂ vs Car
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("🕐 Duration", f"{total_time} min")
        c2.metric("💰 Ticket Fare", f"₹{total_fare:.0f}")
        c3.metric("🔄 Transfers", f"{transfers}")
        c4.metric("🎯 Priority Mode", priority_mode)

        st.markdown("---")
        st.markdown("<div style='font-size:0.9rem; font-weight:700; color:#1e293b; margin-bottom:8px;'>🗺️ Step-by-Step Itinerary</div>", unsafe_allow_html=True)

        # Timeline visualization
        timeline_html = "<div class='timeline'>"
        for i, leg in enumerate(legs, 1):
            mode = leg.get("mode", "LocalBus")
            color = MODE_COLORS.get(mode, "#457B9D")
            icon = MODE_ICONS.get(mode, "🚐")
            route_name = leg.get("route_name", "Transit Line")
            from_stop = leg.get("from_stop", "Origin")
            to_stop = leg.get("to_stop", "Destination")
            dep = leg.get("departure", "--:--")
            arr = leg.get("arrival", "--:--")
            fare = leg.get("fare", 0.0)
            dist = leg.get("distance_km", None)
            dist_str = f" · {dist:.1f} km" if dist else ""
            mins = leg.get("travel_mins", 0)

            if leg.get("is_transfer", False):
                stop_class = "transfer"
                desc = f"<b>🚶 Transfer / Walk:</b> Change platforms/stops ({mins} min buffer)"
            else:
                stop_class = "origin" if i == 1 else "leg"
                desc = (
                    f"<b>{icon} {mode} — {route_name}</b><br/>"
                    f"<span style='color:#475569;'>Board at <b>{from_stop}</b> ({dep}) → Alight at <b>{to_stop}</b> ({arr})</span><br/>"
                    f"<span style='color:#64748b; font-size:0.75rem;'>{mins} mins{dist_str} · Leg Fare: ₹{fare:.0f}</span>"
                )

            timeline_html += f"""
            <div class="timeline-stop {stop_class}">
                {desc}
            </div>
            """
        timeline_html += "</div>"
        st.markdown(timeline_html, unsafe_allow_html=True)

        # Reasoning Log
        render_reasoning_log(reasoning)


def render_reasoning_log(reasoning_trace: list) -> None:
    """
    Render human-readable CSP explanation steps.
    """
    if not reasoning_trace:
        return

    with st.expander("🧠 CSP Constraint Reasoning Log", expanded=False):
        st.markdown(
            "<p style='font-size:0.8rem; color:#64748b; margin-bottom:10px;'>"
            "Demonstration of constraints evaluated, pruned arcs, and objective scoring:</p>",
            unsafe_allow_html=True,
        )
        for i, step in enumerate(reasoning_trace, 1):
            s_lower = step.lower()
            if any(k in s_lower for k in ["pruned", "violat", "discard", "eliminat", "fail"]):
                css_class = "fail"
                icon = "⛔"
            elif any(k in s_lower for k in ["valid", "pass", "survive", "accept", "optimal"]):
                css_class = "pass"
                icon = "✅"
            elif any(k in s_lower for k in ["soft", "penalt", "warn", "peak", "crowd"]):
                css_class = "warn"
                icon = "⚠️"
            else:
                css_class = "info"
                icon = "ℹ️"

            st.markdown(
                f"<div class='reasoning-step {css_class}'>"
                f"<span>{icon}</span>"
                f"<div><b>Rule Check {i}:</b> {step}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )


def build_route_map(
    routes: list,
    center: tuple = (13.08, 80.27),
    zoom: int = 12,
) -> folium.Map:
    """
    Build a Folium map using standard OpenStreetMap (no API key needed).
    """
    m = folium.Map(
        location=center,
        zoom_start=zoom,
        tiles="OpenStreetMap",
        control_scale=True,
    )

    if not routes:
        folium.Marker(
            location=center,
            tooltip="Chennai City Centre",
            popup="<b>Chennai Metropolitan Area</b><br>Choose an origin & destination to plan routes.",
            icon=folium.Icon(color="blue", icon="info-sign"),
        ).add_to(m)
        return m

    # Plot routes
    for r_idx, route in enumerate(routes):
        legs = route.get("legs", [])
        stops = route.get("stops", [])
        opacity = max(1.0 - r_idx * 0.25, 0.4)

        stop_map = {s.get("stop_id"): s for s in stops if s.get("stop_id")}

        # Polylines for each leg
        for leg in legs:
            mode = leg.get("mode", "LocalBus")
            color = MODE_COLORS.get(mode, "#457B9D")

            coords = []
            leg_stops = leg.get("stops", [])
            if leg_stops:
                for ls in leg_stops:
                    lat, lon = ls.get("lat") or ls.get("stop_lat"), ls.get("lon") or ls.get("stop_lon")
                    if lat and lon:
                        coords.append((float(lat), float(lon)))
            else:
                for key in ("from_stop_id", "to_stop_id"):
                    sid = leg.get(key)
                    if sid and sid in stop_map:
                        s = stop_map[sid]
                        lat, lon = s.get("lat") or s.get("stop_lat"), s.get("lon") or s.get("stop_lon")
                        if lat and lon:
                            coords.append((float(lat), float(lon)))

            if len(coords) >= 2:
                weight = 6 if r_idx == 0 else 4
                folium.PolyLine(
                    locations=coords,
                    color=color,
                    weight=weight,
                    opacity=opacity,
                    dash_array="5, 10" if leg.get("is_transfer") else None,
                    tooltip=f"Route #{r_idx+1}: {mode} ({leg.get('route_name', '')})",
                ).add_to(m)

        # Plot origin, destination and transfers for the top recommended route
        if r_idx == 0 and stops:
            first_stop = stops[0]
            last_stop = stops[-1]

            if first_stop.get("lat") and first_stop.get("lon"):
                folium.Marker(
                    location=(float(first_stop["lat"]), float(first_stop["lon"])),
                    tooltip=f"🟢 Start: {first_stop.get('stop_name', 'Origin')}",
                    icon=folium.Icon(color="green", icon="play", prefix="fa"),
                ).add_to(m)

            if last_stop.get("lat") and last_stop.get("lon"):
                folium.Marker(
                    location=(float(last_stop["lat"]), float(last_stop["lon"])),
                    tooltip=f"🔴 End: {last_stop.get('stop_name', 'Destination')}",
                    icon=folium.Icon(color="red", icon="flag", prefix="fa"),
                ).add_to(m)

            # Intermediate transfer nodes
            for s in stops[1:-1]:
                if s.get("lat") and s.get("lon"):
                    folium.CircleMarker(
                        location=(float(s["lat"]), float(s["lon"])),
                        radius=5,
                        color="#312e81",
                        fill=True,
                        fill_color="#6366f1",
                        fill_opacity=0.9,
                        tooltip=f"🚏 Stop: {s.get('stop_name')}",
                    ).add_to(m)

    # Add interactive fullscreen control
    plugins.Fullscreen(position="topright").add_to(m)

    # HTML floating legend
    legend_html = """
    <div style="position: fixed; bottom: 25px; left: 25px; z-index: 999;
                background: rgba(255, 255, 255, 0.95); backdrop-filter: blur(5px);
                padding: 10px 14px; border-radius: 10px; border: 1px solid #cbd5e1;
                box-shadow: 0 4px 14px rgba(0,0,0,0.15); font-family: sans-serif; font-size: 12px;">
      <b style="color:#0f172a;">Transit Legend</b><br/>
      <div style="margin-top:4px;"><span style="color:#E63946; font-size:16px;">━</span> <b>Metro (CMRL)</b></div>
      <div><span style="color:#457B9D; font-size:16px;">━</span> <b>MTC Bus</b></div>
      <div><span style="color:#E9C46A; font-size:16px;">━</span> <b>Suburban Rail</b></div>
      <div><span style="color:#6c757d; font-size:16px;">┅</span> <b>Transfer / Walk</b></div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    return m


def render_network_stats(stats: dict):
    """
    Render summary KPI cards for network explorer.
    """
    st.write(stats)
