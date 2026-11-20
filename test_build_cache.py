import time
from engine.graph_builder import TransitGraphBuilder
from engine.router import ConstrainedRouter

t0 = time.time()
builder = TransitGraphBuilder("data/chennai_transit.db")
g = builder.build_graph(force_rebuild=True)
print(f"Graph built and cached in {time.time()-t0:.2f}s. Nodes: {g.number_of_nodes()}, Edges: {g.number_of_edges()}")

# Test fast reload from cache
t1 = time.time()
g2 = builder.build_graph(force_rebuild=False)
print(f"Reload from cache took {time.time()-t1:.4f}s!")

# Test route search
router = ConstrainedRouter(g2, "data/chennai_transit.db")

# Search stops
central_stops = builder.get_stop_by_name("Central")
airport_stops = builder.get_stop_by_name("Airport")
print(f"Central matches: {len(central_stops)}, Airport matches: {len(airport_stops)}")

c_id = central_stops[0]["stop_id"]
a_id = airport_stops[0]["stop_id"]
print(f"Origin: {central_stops[0]['stop_name']} ({c_id})")
print(f"Dest: {airport_stops[0]['stop_name']} ({a_id})")

prefs = {"wheelchair_required": False, "max_budget": 200, "max_transfers": 3, "priority_mode": "balanced"}
t2 = time.time()
routes = router.find_routes(c_id, a_id, "08:00", prefs)
print(f"Routing completed in {time.time()-t2:.4f}s. Routes found: {len(routes)}")

for idx, r in enumerate(routes, 1):
    print(f"\n--- Route {idx} ---")
    print(f"Total time: {r['total_time_mins']} mins | Fare: ₹{r['total_fare']} | Transfers: {r['num_transfers']}")
    for leg in r["legs"]:
        print(f"  [{leg['mode']}] {leg['from_stop']} -> {leg['to_stop']} via {leg['route_name']} ({leg['departure']} - {leg['arrival']})")
