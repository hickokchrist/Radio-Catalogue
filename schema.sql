PRAGMA foreign_keys = ON;

CREATE TABLE artists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    alias TEXT
);

CREATE TABLE songs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    country TEXT,
    alias TEXT,
    genre TEXT,
	duration INTEGER,
    language TEXT,
    notes TEXT
);

CREATE TABLE song_artists (
    song_id INTEGER NOT NULL,
    artist_id INTEGER NOT NULL,
    role TEXT,
    PRIMARY KEY (song_id, artist_id),
    FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE,
    FOREIGN KEY (artist_id) REFERENCES artists(id) ON DELETE CASCADE
);


CREATE INDEX idx_artists_name ON artists(name);
CREATE INDEX idx_songs_title ON songs(title);
CREATE INDEX idx_song_artists_song_id ON song_artists(song_id);
CREATE INDEX idx_song_artists_artist_id ON song_artists(artist_id);