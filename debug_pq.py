import pickle
import heapq
from engine.router import ConstrainedRouter, TRANSFER_BUFFER_MINS, _mins_to_time

with open("data/transit_network.pickle", "rb") as f:
    G = pickle.load(f)["graph"]

router = ConstrainedRouter(G, "data/chennai_transit.db")
c_id = "MTC-10303"
a_id = "CMRL-117_1"
start_mins = 480
max_transfers = 3
max_budget = 200

valid_stops = router.ac3_prune(c_id, a_id, {})

# Let's inspect the BFS
heap = [(0.0, start_mins, c_id, None, 0, 0.0, 0.0, [c_id], [])]
best_cost = {}
steps = 0
found = []

while heap and steps < 10000:
    steps += 1
    cost, cur_time, cur_stop, cur_route, transfers, fare, penalty, path_stops, path_edges = heapq.heappop(heap)
    
    if cur_stop == a_id:
        print(f"FOUND destination at step {steps}! Duration: {cur_time - start_mins} mins, transfers: {transfers}, fare: {fare}")
        found.append((cur_time - start_mins, transfers, fare, path_stops))
        break

    state_key = (cur_stop, cur_route)
    if state_key in best_cost and best_cost[state_key] < cost - 1.0:
        continue
    best_cost[state_key] = cost

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
        nxt_cost = (arr_m - start_mins) + nxt_transfers * 10
        
        nxt_state_key = (nxt, nxt_route)
        if nxt_state_key in best_cost and best_cost[nxt_state_key] <= nxt_cost:
            continue

        heapq.heappush(heap, (nxt_cost, arr_m, nxt, nxt_route, nxt_transfers, nxt_fare, 0.0, path_stops + [nxt], path_edges + [edge]))

print(f"Total steps: {steps}, Queue size: {len(heap)}, Found count: {len(found)}")
