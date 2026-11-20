import pickle
import heapq
import math

with open("data/transit_network.pickle", "rb") as f:
    G = pickle.load(f)["graph"]

c_id = "MTC-10303"
a_id = "CMRL-117_1"
dest_node = G.nodes[a_id]
dest_lat, dest_lon = dest_node["lat"], dest_node["lon"]

def heuristic_mins(u):
    u_node = G.nodes[u]
    lat, lon = u_node["lat"], u_node["lon"]
    # distance in km
    dlat = (dest_lat - lat) * 111.0
    dlon = (dest_lon - lon) * 111.0 * 0.97
    dist_km = math.sqrt(dlat**2 + dlon**2)
    # Transit travel speed ~ 30 km/h -> 2 mins per km
    return dist_km * 2.0

start_mins = 480
max_transfers = 3
max_budget = 200

# A* Priority Queue: (f_score, g_cost, cur_time, cur_stop, cur_route, transfers, fare, path)
h0 = heuristic_mins(c_id)
heap = [(h0, 0.0, start_mins, c_id, None, 0, 0.0, [c_id], [])]
best_g = {}
steps = 0
found = []

while heap and steps < 10000 and len(found) < 3:
    steps += 1
    f_score, g_cost, cur_time, cur_stop, cur_route, transfers, fare, path_stops, path_edges = heapq.heappop(heap)
    
    if cur_stop == a_id:
        print(f"A* FOUND route #{len(found)+1} at step {steps}! Duration: {cur_time - start_mins} mins, transfers: {transfers}, fare: ₹{fare}")
        found.append((cur_time - start_mins, transfers, fare, path_stops))
        continue

    state_key = (cur_stop, cur_route)
    if state_key in best_g and best_g[state_key] <= g_cost:
        continue
    best_g[state_key] = g_cost

    for nxt in G.successors(cur_stop):
        if nxt in path_stops:
            continue
        edge = G.get_edge_data(cur_stop, nxt)
        is_xfer = edge.get("is_transfer", False)
        nxt_route = edge.get("route_id", "")
        travel_m = edge.get("travel_mins", 3)
        leg_fare = float(edge.get("fare", 0.0))
        
        is_line_change = (cur_route is not None and cur_route != nxt_route and not is_xfer)
        nxt_transfers = transfers + (1 if (is_line_change or is_xfer) else 0)
        if nxt_transfers > max_transfers:
            continue

        nxt_fare = fare + leg_fare
        if nxt_fare > max_budget:
            continue

        arr_m = cur_time + travel_m
        nxt_g = g_cost + travel_m + (nxt_transfers * 8.0)
        nxt_f = nxt_g + heuristic_mins(nxt)
        
        nxt_state_key = (nxt, nxt_route)
        if nxt_state_key in best_g and best_g[nxt_state_key] <= nxt_g:
            continue

        heapq.heappush(heap, (nxt_f, nxt_g, arr_m, nxt, nxt_route, nxt_transfers, nxt_fare, path_stops + [nxt], path_edges + [edge]))

print(f"Done! Total steps: {steps}, Found count: {len(found)}")
