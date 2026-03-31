#!/usr/bin/env python3
"""
backfill_aliases.py — Romanize missing aliases in catalogue.db
Imports romanize() from add_song.py and updates any songs or artists
where the name contains non-ASCII characters but alias is empty.
Then redumps data.sql.

Usage:
    python backfill_aliases.py
"""

import sqlite3
import sys
import os

# Reuse logic from add_song.py
sys.path.insert(0, os.path.dirname(__file__))
from add_song import needs_romanization, romanize

DB_FILE = "catalogue.db"
DATA_SQL = "data.sql"


def backfill(conn, table, name_col="name"):
    cursor = conn.cursor()
    cursor.execute(f"SELECT id, {name_col}, alias FROM {table}")
    rows = cursor.fetchall()

    updated = 0
    for row_id, name, alias in rows:
        if needs_romanization(name) and not alias:
            romanized = romanize(name)
            if romanized and romanized != name:
                cursor.execute(
                    f"UPDATE {table} SET alias = ? WHERE id = ?",
                    (romanized, row_id)
                )
                print(f"  ✓  [{table}] {name} → {romanized}")
                updated += 1
            else:
                print(f"  ⚠  [{table}] {name} — could not romanize (library missing?)")

    return updated


def dump_data_sql(conn):
    with open(DATA_SQL, "w", encoding="utf-8") as f:
        f.write("PRAGMA foreign_keys = ON;\n\n")
        for table in ["artists", "songs", "song_artists"]:
            for row in conn.execute(f"SELECT * FROM {table}"):
                values = ", ".join(
                    "NULL" if v is None
                    else str(v) if isinstance(v, int)
                    else "'" + str(v).replace("'", "''") + "'"
                    for v in row
                )
                f.write(f"INSERT INTO {table} VALUES ({values});\n")
    print(f"\n  ✓  {DATA_SQL} updated")


def main():
    if not os.path.exists(DB_FILE):
        print(f"✗  {DB_FILE} not found.")
        sys.exit(1)

    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA foreign_keys = ON")

    print("\n── Backfilling aliases ─────────────────────")
    total = 0
    total += backfill(conn, "artists", name_col="name")
    total += backfill(conn, "songs",   name_col="title")

    if total == 0:
        print("  Nothing to update — all aliases already filled or no romanization libraries available.")
    else:
        conn.commit()
        print(f"\n  {total} alias(es) updated")

    print("\n── Dumping data.sql ────────────────────────")
    dump_data_sql(conn)
    conn.close()

    print("\n  Next steps:")
    print("    git add data.sql")
    print("    git commit -m \"Backfill romanized aliases\"")
    print()


if __name__ == "__main__":
    main()
