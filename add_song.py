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
        import pykakasi
        kks = pykakasi.kakasi()
        result = kks.convert(text)
        return " ".join(item['hepburn'] for item in result)
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
# Duration utilities
# -------------------------------

def parse_duration(raw):
    """Accept m:ss or raw integer seconds. Returns integer or None."""
    if not raw:
        return None
    raw = raw.strip()
    if ':' in raw:
        parts = raw.split(':')
        try:
            minutes, seconds = int(parts[0]), int(parts[1])
            return minutes * 60 + seconds
        except (ValueError, IndexError):
            print("  ⚠  Could not parse duration — expected m:ss or whole seconds. Skipping.")
            return None
    else:
        try:
            return int(raw)
        except ValueError:
            print("  ⚠  Could not parse duration — expected m:ss or whole seconds. Skipping.")
            return None


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
    """Return SQL-safe quoted string, integer, or NULL."""
    if s is None:
        return "NULL"
    if isinstance(s, int):
        return str(s)
    if s.strip() == "":
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

    # New artist — generate alias if non-ASCII
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


def get_or_create_song(cursor, title, country, genre, duration, language, notes):
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
        "INSERT INTO songs (title, country, alias, genre, duration, language, notes) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (title, country or None, alias, genre or None, duration, language or None, notes or None)
    )
    song_id = cursor.lastrowid

    append_to_data_sql(
        f"INSERT INTO songs (title, country, alias, genre, duration, language, notes) VALUES "
        f"('{escape(title)}', {sql_text(country)}, {sql_text(alias)}, {sql_text(genre)}, "
        f"{sql_text(duration)}, {sql_text(language)}, {sql_text(notes)});\n"
    )

    return song_id


def link_artist_to_song(cursor, song_id, artist_id, role):
    cursor.execute(
        "INSERT OR IGNORE INTO song_artists (song_id, artist_id, role) VALUES (?, ?, ?)",
        (song_id, artist_id, role or None)
    )

    title = cursor.execute(
        "SELECT title FROM songs WHERE id=?", (song_id,)
    ).fetchone()[0]

    artist = cursor.execute(
        "SELECT name FROM artists WHERE id=?", (artist_id,)
    ).fetchone()[0]

    append_to_data_sql(
        f"""INSERT OR IGNORE INTO song_artists (song_id, artist_id, role)
SELECT s.id, a.id, {sql_text(role)}
FROM songs s, artists a
WHERE s.rowid = (
    SELECT MAX(rowid) FROM songs WHERE title = '{escape(title)}'
)
AND a.name = '{escape(artist)}';\n"""
    )


# -------------------------------
# Main CLI
# -------------------------------

def main():
    if not os.path.exists(SCHEMA_SQL):
        print(f"✗  {SCHEMA_SQL} not found. Make sure you're in your project folder.")
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
            f.write("-- To rebuild: sqlite3 catalogue.db < schema.sql && sqlite3 catalogue.db < data.sql\n\n")
            f.write("PRAGMA foreign_keys = ON;\n\n")

    print("\n── Add a Song ──────────────────────────────")

    title        = prompt("Title", required=True)
    primary      = prompt("Primary artist(s) — comma-separated", required=True)
    featured     = prompt("Featured artist(s) — optional")
    genre        = prompt("Genre (optional)")
    duration_raw = prompt("Duration — m:ss or seconds (optional)")
    language     = prompt("Language (optional)")
    country      = prompt("Country (optional, applies to the song)")
    notes        = prompt("Notes (optional)")

    # Parse duration to integer seconds
    duration = parse_duration(duration_raw)

    # Parse artists and assign roles
    primary_list  = [a.strip() for a in primary.split(",") if a.strip()]
    featured_list = [a.strip() for a in featured.split(",") if a.strip()] if featured else []

    artist_list = primary_list + featured_list
    roles       = ["primary"] * len(primary_list) + ["featured"] * len(featured_list)

    # Write comment block to data.sql
    append_to_data_sql(f"\n-- [{datetime.now().strftime('%Y-%m-%d')}] {title} — {', '.join(artist_list)}\n")

    # Insert song
    song_id = get_or_create_song(cursor, title, country, genre, duration, language, notes)

    # Insert artists and bridge links
    for artist, role in zip(artist_list, roles):
        artist_id = get_or_create_artist(cursor, artist)
        link_artist_to_song(cursor, song_id, artist_id, role)

    # Update title to include featured artists in display
    display_title = build_display_title(title, featured_list)
    if display_title != title:
        cursor.execute("UPDATE songs SET title = ? WHERE id = ?", (display_title, song_id))
        append_to_data_sql(
            f"UPDATE songs SET title = '{escape(display_title)}' "
            f"WHERE title = '{escape(title)}';\n"
        )

    conn.commit()
    conn.close()

    credit = ', '.join(primary_list)
    if featured_list:
        credit += f" ft. {', '.join(featured_list)}"

    print(f"\n  ✓  Added \"{display_title}\" by {credit}")
    print(f"  ✓  data.sql updated\n")
    print()


if __name__ == "__main__":
    main()