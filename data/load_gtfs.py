"""
load_gtfs.py
------------
Reads all GTFS .txt files from the chennai-unified-gtfs/ folder (relative to
the project root) and loads them into a SQLite database at data/chennai_transit.db.

Tables created:
  agencies, stops, routes, trips, stop_times,
  fare_attributes, fare_rules, transfers, calendar

Indexes are added on stop_id, route_id, and trip_id for query performance.
stop_times.txt (55 MB) is loaded in chunks of 10 000 rows.
"""

import os
import sqlite3
import csv
import io
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
GTFS_DIR = PROJECT_ROOT / "chennai-unified-gtfs"
DB_PATH = PROJECT_ROOT / "data" / "chennai_transit.db"


# ---------------------------------------------------------------------------
# GTFS file → table mapping
# ---------------------------------------------------------------------------
FILE_TABLE_MAP = {
    "agency.txt":          "agencies",
    "stops.txt":           "stops",
    "routes.txt":          "routes",
    "trips.txt":           "trips",
    "stop_times.txt":      "stop_times",
    "fare_attributes.txt": "fare_attributes",
    "fare_rules.txt":      "fare_rules",
    "transfers.txt":       "transfers",
    "calendar.txt":        "calendar",
}

# Files that should be loaded in chunks (large files)
CHUNKED_FILES = {"stop_times.txt"}
CHUNK_SIZE = 10_000


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_gtfs_file(filepath: Path):
    """
    Read a GTFS .txt file and return (headers, rows) where rows is a list of
    dicts.  Uses utf-8 with errors='replace' to handle bad bytes gracefully.
    """
    with open(filepath, encoding="utf-8", errors="replace", newline="") as fh:
        reader = csv.DictReader(fh)
        headers = reader.fieldnames or []
        rows = list(reader)
    return headers, rows


def _read_gtfs_file_chunked(filepath: Path, chunk_size: int = CHUNK_SIZE):
    """
    Generator that yields (headers, chunk) tuples for large GTFS files.
    Each chunk is a list of dicts of at most chunk_size rows.
    """
    with open(filepath, encoding="utf-8", errors="replace", newline="") as fh:
        reader = csv.DictReader(fh)
        headers = reader.fieldnames or []
        chunk: list = []
        for i, row in enumerate(reader, start=1):
            chunk.append(row)
            if i % chunk_size == 0:
                yield headers, chunk
                chunk = []
        if chunk:
            yield headers, chunk


def _create_table(conn: sqlite3.Connection, table: str, headers: list[str]):
    """Create a table with TEXT columns for every GTFS field."""
    cols = ", ".join(f'"{h}" TEXT' for h in headers)
    conn.execute(f'CREATE TABLE IF NOT EXISTS "{table}" ({cols})')
    conn.commit()


def _insert_rows(conn: sqlite3.Connection, table: str, headers: list[str], rows: list[dict]):
    """Bulk-insert rows into the given table."""
    if not rows:
        return
    placeholders = ", ".join("?" for _ in headers)
    col_names = ", ".join(f'"{h}"' for h in headers)
    sql = f'INSERT INTO "{table}" ({col_names}) VALUES ({placeholders})'
    data = [tuple(row.get(h, "") for h in headers) for row in rows]
    conn.executemany(sql, data)
    conn.commit()


def _add_indexes(conn: sqlite3.Connection):
    """Add performance indexes on the most-queried columns."""
    index_specs = [
        # (table, column)
        ("stops",       "stop_id"),
        ("routes",      "route_id"),
        ("trips",       "trip_id"),
        ("trips",       "route_id"),
        ("stop_times",  "stop_id"),
        ("stop_times",  "trip_id"),
        ("fare_rules",  "route_id"),
        ("transfers",   "from_stop_id"),
        ("transfers",   "to_stop_id"),
    ]
    for table, col in index_specs:
        idx_name = f"idx_{table}_{col}"
        try:
            conn.execute(
                f'CREATE INDEX IF NOT EXISTS "{idx_name}" ON "{table}" ("{col}")'
            )
        except sqlite3.OperationalError as exc:
            # Table may not exist if the file was absent; skip gracefully
            print(f"  [warn] Could not create index {idx_name}: {exc}")
    conn.commit()


def _row_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """Return a dict of {table_name: row_count} for every loaded table."""
    counts: dict[str, int] = {}
    for table in FILE_TABLE_MAP.values():
        try:
            cur = conn.execute(f'SELECT COUNT(*) FROM "{table}"')
            counts[table] = cur.fetchone()[0]
        except sqlite3.OperationalError:
            counts[table] = -1  # table was not created (file missing)
    return counts


# ---------------------------------------------------------------------------
# Main loader
# ---------------------------------------------------------------------------

def load_gtfs(gtfs_dir: Path = GTFS_DIR, db_path: Path = DB_PATH):
    """Load all GTFS files into the SQLite database."""
    db_path.parent.mkdir(parents=True, exist_ok=True)

    if db_path.exists():
        print(f"Removing existing database: {db_path}")
        db_path.unlink()

    print(f"Loading GTFS data from : {gtfs_dir}")
    print(f"Writing database to    : {db_path}\n")

    conn = sqlite3.connect(str(db_path))
    # Increase performance: WAL mode + a generous cache
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA cache_size=-32000")   # ~32 MB page cache
    conn.execute("PRAGMA synchronous=NORMAL")

    for filename, table in FILE_TABLE_MAP.items():
        filepath = gtfs_dir / filename
        if not filepath.exists():
            print(f"  [skip] {filename} not found — table '{table}' will be empty")
            continue

        if filename in CHUNKED_FILES:
            print(f"  Loading {filename} → {table}  (chunked, chunksize={CHUNK_SIZE}) …")
            first_chunk = True
            total_rows = 0
            for headers, chunk in _read_gtfs_file_chunked(filepath, CHUNK_SIZE):
                if first_chunk:
                    _create_table(conn, table, headers)
                    first_chunk = False
                _insert_rows(conn, table, headers, chunk)
                total_rows += len(chunk)
                print(f"    … {total_rows:,} rows inserted", end="\r", flush=True)
            print(f"    Done — {total_rows:,} rows inserted           ")
        else:
            print(f"  Loading {filename} → {table} …")
            headers, rows = _read_gtfs_file(filepath)
            _create_table(conn, table, headers)
            _insert_rows(conn, table, headers, rows)
            print(f"    Done — {len(rows):,} rows inserted")

    print("\nBuilding indexes …")
    _add_indexes(conn)
    print("Indexes created.\n")

    # Summary
    counts = _row_counts(conn)
    conn.close()

    db_size_mb = db_path.stat().st_size / (1024 * 1024)

    print("=" * 50)
    print("Load complete — row counts per table:")
    print("-" * 50)
    for table, count in counts.items():
        status = f"{count:>10,}" if count >= 0 else "   (missing)"
        print(f"  {table:<20} {status}")
    print("-" * 50)
    print(f"  Database size: {db_size_mb:.2f} MB")
    print("=" * 50)

    return counts, db_size_mb


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    load_gtfs()
