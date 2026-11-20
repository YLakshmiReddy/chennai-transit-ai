import pickle
import networkx as nx

with open("data/transit_network.pickle", "rb") as f:
    G = pickle.load(f)["graph"]

c_id = "MTC-10303"
a_id = "CMRL-117_1"

print("c_id in G:", c_id in G, "out_degree:", G.out_degree(c_id))
print("a_id in G:", a_id in G, "in_degree:", G.in_degree(a_id))

# Is there any path in G between c_id and a_id?
has_path = nx.has_path(G, c_id, a_id)
print(f"Path between {c_id} and {a_id} exists:", has_path)

if has_path:
    p = nx.shortest_path(G, c_id, a_id)
    print("Shortest path length:", len(p))
    for node in p[:10]:
        print("  Node:", node, G.nodes[node]["stop_name"], G.nodes[node]["agency_id"])
else:
    # Check connected components or reachable sets
    fwd = nx.descendants(G, c_id)
    print(f"Descendants from {c_id}:", len(fwd))
    bwd = nx.ancestors(G, a_id)
    print(f"Ancestors to {a_id}:", len(bwd))
    intersection = fwd & bwd
    print(f"Intersection count: {len(intersection)}")
    
    # Check nearest stops to c_id and a_id
    c_lat, c_lon = G.nodes[c_id]["lat"], G.nodes[c_id]["lon"]
    print(f"c_id coords: {c_lat}, {c_lon}")
    # find closest CMRL stop to c_id
    min_d = 999999
    closest = None
    import math
    for n, d in G.nodes(data=True):
        if n.startswith("CMRL"):
            dist = math.hypot(d["lat"] - c_lat, d["lon"] - c_lon) * 111000
            if dist < min_d:
                min_d = dist
                closest = (n, d["stop_name"])
    print(f"Closest CMRL to {c_id}: {closest} at {min_d:.1f} meters")
