import pickle
from engine.router import ConstrainedRouter

with open("data/transit_network.pickle", "rb") as f:
    G = pickle.load(f)["graph"]

router = ConstrainedRouter(G, "data/chennai_transit.db")
c_id = "MTC-10303"
a_id = "CMRL-117_1"

prefs = {"wheelchair_required": False, "max_budget": 200, "max_transfers": 3, "priority_mode": "balanced"}
valid = router.ac3_prune(c_id, a_id, prefs)
print(f"Candidates from ac3_prune: {len(valid)}")
print("c_id in valid:", c_id in valid, "a_id in valid:", a_id in valid)

routes = router.find_routes(c_id, a_id, "08:00", prefs)
print(f"Routes found: {len(routes)}")
