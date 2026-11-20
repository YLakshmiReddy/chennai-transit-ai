import time
import sqlite3
from engine.graph_builder import TransitGraphBuilder
from engine.router import ConstrainedRouter

builder = TransitGraphBuilder('data/chennai_transit.db')
g = builder.build_graph()

conn = sqlite3.connect('data/chennai_transit.db')
c = conn.cursor()
c.execute("SELECT stop_id, stop_name FROM stops WHERE stop_name LIKE '%Central%' AND stop_id LIKE 'CMRL%'")
central = c.fetchall()
print('Metro Central stops:', central)

c.execute("SELECT stop_id, stop_name FROM stops WHERE stop_name LIKE '%Airport%' AND stop_id LIKE 'CMRL%'")
airport = c.fetchall()
print('Metro Airport stops:', airport)

if central and airport:
    router = ConstrainedRouter(g, 'data/chennai_transit.db')
    prefs = {'wheelchair_required': False, 'max_budget': 200, 'max_transfers': 3, 'priority_mode': 'balanced'}
    routes = router.find_routes(central[0][0], airport[0][0], '08:00', prefs)
    print('Metro routes found:', len(routes))
    for r in routes:
        print('Route:', r['total_time_mins'], 'mins, fare: ₹', r['total_fare'], 'legs:', len(r['legs']))
        for leg in r['legs']:
            print('  Leg:', leg['from_stop'], '->', leg['to_stop'], leg['mode'], leg['departure'], leg['arrival'])
conn.close()
