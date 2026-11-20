import sqlite3
import os

db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chennai_transit.db")
conn = sqlite3.connect(db_path)
c = conn.cursor()

c.execute("PRAGMA table_info(stops)")
cols = [r[1] for r in c.fetchall()]

if "wheelchair_boarding" not in cols:
    c.execute("ALTER TABLE stops ADD COLUMN wheelchair_boarding INTEGER DEFAULT 0")
    print("Added wheelchair_boarding column")

if "wheelchair_accessible" not in cols:
    c.execute("ALTER TABLE stops ADD COLUMN wheelchair_accessible INTEGER DEFAULT 0")
    print("Added wheelchair_accessible column")

c.execute("UPDATE stops SET wheelchair_boarding = 1, wheelchair_accessible = 1 WHERE stop_id LIKE 'CMRL%' OR stop_id LIKE 'SRR%'")

c.execute("PRAGMA table_info(transfers)")
t_cols = [r[1] for r in c.fetchall()]
if "min_transfer_time" not in t_cols:
    c.execute("ALTER TABLE transfers ADD COLUMN min_transfer_time INTEGER DEFAULT 300")
    print("Added min_transfer_time column")

conn.commit()

c.execute("SELECT COUNT(*) FROM stops WHERE wheelchair_accessible = 1")
print("Total accessible stops:", c.fetchone()[0])
conn.close()
