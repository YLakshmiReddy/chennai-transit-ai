import time
import pickle
from engine.router import ConstrainedRouter

with open("data/transit_network.pickle", "rb") as f:
    G = pickle.load(f)["graph"]

router = ConstrainedRouter(G, "data/chennai_transit.db")
prefs = {"wheelchair_required": False, "max_budget": 200, "max_transfers": 3, "priority_mode": "balanced"}

t0 = time.time()
routes = router.find_routes("MTC-10303", "CMRL-117_1", "08:00", prefs)
print(f"Routing completed in {time.time()-t0:.3f}s. Routes found: {len(routes)}")
for i, r in enumerate(routes, 1):
    print(f"Route {i}: {r['total_time_mins']} mins, ₹{r['total_fare']}, {r['num_transfers']} transfers, {len(r['legs'])} legs")
    for leg in r['legs']:
        print(f"  [{leg['mode']}] {leg['from_stop']} -> {leg['to_stop']} ({leg['departure']} - {leg['arrival']})")
