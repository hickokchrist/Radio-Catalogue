#!/usr/bin/env python3
"""
add_song.py — Radio Catalogue CLI
Adds a song entry to catalogue.db and appends the corresponding
INSERT statements to data.sql for reproducibility.

Usage:
    python add_song.py
"""

import sqlite3
import os
import sys
import re
from datetime import datetime

DB_FILE = "catalogue.db"
DATA_SQL = "data.sql"
SCHEMA_SQL = "schema.sql"

# -------------------------------
# Romanization utilities
# -------------------------------
def build_display_title(raw_title, featured_list):
    if not featured_list:
        return raw_title
    return f"{raw_title} (feat. {', '.join(featured_list)})"
    
def needs_romanization(s):
    return bool(re.search(r'[^\u0000-\u007F]', s))

def romanize(text):
    # Cyrillic → Latin
    try:
        from transliterate import translit
        return translit(text, 'ru', reversed=True)
    except Exception:
        pass

    # Japanese → Romaji
    try:
        from romkan import to_roma
        return to_roma(text)
    except Exception:
        pass

    # Korean → RR
    try:
        from hangul_romanize import Transliter
        from hangul_romanize.rule import academic
        t = Transliter(academic)
        return t.translit(text)
    except Exception:
        pass

    # Chinese → Pinyin
    try:
        from pypinyin import lazy_pinyin
        return " ".join(lazy_pinyin(text))
    except Exception:
        pass

    # Default: return unchanged
    return text


# -------------------------------
# Utility functions
# -------------------------------

def append_to_data_sql(line):
    with open(DATA_SQL, "a", encoding="utf-8") as f:
        f.write(line)

def escape(s):
    if s is None:
        return ""
    return s.replace("'", "''")

def sql_text(s):
    if s is None or (isinstance(s, str) and s.strip() == ""):
        return "NULL"
    return f"'{escape(s.strip())}'"

def prompt(label, required=False):
    while True:
        val = input(f"  {label}: ").strip()
        if val or not required:
            return val if val else None
        print(f"  ✗  {label} is required.")


# -------------------------------
# Database operations
# -------------------------------

def get_or_create_artist(cursor, name):
    name = name.strip()
    cursor.execute("SELECT id FROM artists WHERE name = ?", (name,))
    row = cursor.fetchone()

    if row:
        return row[0]

    # New artist
    alias = romanize(name) if needs_romanization(name) else None

    cursor.execute(
        "INSERT INTO artists (name, alias) VALUES (?, ?)",
        (name, alias)
    )
    artist_id = cursor.lastrowid

    append_to_data_sql(
        f"INSERT INTO artists (name, alias) VALUES "
        f"('{escape(name)}', {sql_text(alias)});\n"
    )

    return artist_id


def get_or_create_song(cursor, title, genre, language, notes, country):
    cursor.execute("SELECT id FROM songs WHERE title = ?", (title,))
    existing = cursor.fetchall()

    if existing:
        print(f"\n  ⚠  A song titled \"{title}\" already exists.")
        confirm = input("     Add anyway? (y/n): ").strip().lower()
        if confirm != 'y':
            print("  Cancelled.")
            sys.exit(0)

    alias = romanize(title) if needs_romanization(title) else None

    cursor.execute(
        "INSERT INTO songs (title, genre, language, notes, alias, country) VALUES (?, ?, ?, ?, ?, ?)",
        (title, genre or None, language or None, notes or None, alias, country or None)
    )
    song_id = cursor.lastrowid

    append_to_data_sql(
        f"INSERT INTO songs (title, genre, language, notes, alias, country) VALUES "
        f"('{escape(title)}', {sql_text(genre)}, {sql_text(language)}, "
        f"{sql_text(notes)}, {sql_text(alias)}, {sql_text(country)});\n"
    )

    return song_id


def link_artist_to_song(cursor, song_id, artist_id, role):
    cursor.execute(
        "INSERT OR IGNORE INTO song_artists (song_id, artist_id, role) VALUES (?, ?, ?)",
        (song_id, artist_id, role or None)
    )

    # Build reproducible SQL
    title = cursor.execute(
        "SELECT title FROM songs WHERE id=?", (song_id,)
    ).fetchone()[0]

    artist = cursor.execute(
        "SELECT name FROM artists WHERE id=?", (artist_id,)
    ).fetchone()[0]

    append_to_data_sql(
        f"""
INSERT OR IGNORE INTO song_artists (song_id, artist_id, role)
SELECT s.id, a.id, {sql_text(role)}
FROM songs s, artists a
WHERE s.rowid = (
    SELECT MAX(rowid)
    FROM songs
    WHERE title = '{escape(title)}'
)
AND a.name = '{escape(artist)}';
"""
    )


# -------------------------------
# Main CLI
# -------------------------------

def main():
    if not os.path.exists(SCHEMA_SQL):
        print(f"✗  {SCHEMA_SQL} not found.")
        sys.exit(1)

    db_existed = os.path.exists(DB_FILE)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")

    if not db_existed:
        print(f"  Creating new database from {SCHEMA_SQL}...")
        with open(SCHEMA_SQL, "r", encoding="utf-8") as f:
            conn.executescript(f.read())

    if not os.path.exists(DATA_SQL):
        with open(DATA_SQL, "w", encoding="utf-8") as f:
            f.write("-- Radio Catalogue data\n")
            f.write("-- Auto-generated by add_song.py\n")
            f.write("PRAGMA foreign_keys = ON;\n\n")

    print("\n── Add a Song ──────────────────────────────")

    title    = prompt("Title", required=True)
    primary  = prompt("Primary artist(s) — comma-separated", required=True)
    featured = prompt("Featured artist(s) — optional")
    genre    = prompt("Genre (optional)")
    language = prompt("Language (optional)")
    country  = prompt("Country (optional, applies to the song)")
    notes    = prompt("Notes (optional)")

    primary_list  = [a.strip() for a in primary.split(",") if a.strip()]
    featured_list = [a.strip() for a in featured.split(",") if a.strip()] if featured else []

    artist_list = primary_list + featured_list
    roles       = ["primary"] * len(primary_list) + ["featured"] * len(featured_list)

    append_to_data_sql(f"\n-- [{datetime.now().strftime('%Y-%m-%d')}] {title} — {', '.join(artist_list)}\n")

    song_id = get_or_create_song(cursor, title, genre, language, notes, country)

    for artist, role in zip(artist_list, roles):
        artist_id = get_or_create_artist(cursor, artist)
        link_artist_to_song(cursor, song_id, artist_id, role)

# After linking artists, update the song title to include featured artists
    display_title = build_display_title(title, featured_list)

    cursor.execute(
    "UPDATE songs SET title = ? WHERE id = ?",
    (display_title, song_id)
)

    append_to_data_sql(
    f"UPDATE songs SET title = '{escape(display_title)}' WHERE title = '{escape(title)}';\n"
)

    title = display_title  # update for final printout

    conn.commit()
    conn.close()

    credit = ', '.join(primary_list)
    if featured_list:
        credit += f" ft. {', '.join(featured_list)}"

    print(f"\n  ✓  Added \"{title}\" by {credit}")
    print(f"  ✓  data.sql updated\n")


if __name__ == "__main__":
    main()