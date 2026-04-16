.mode csv
.headers on
.output catalogue.csv
SELECT 
    songs.title,
    songs.alias,
    GROUP_CONCAT(artists.name, ', ') AS artists,
    GROUP_CONCAT(artists.alias, ', ') AS artist_aliases,
    songs.country,
    songs.genre,
    songs.language,
    songs.duration,
    songs.notes
FROM songs
JOIN song_artists ON songs.id = song_artists.song_id
JOIN artists ON artists.id = song_artists.artist_id
GROUP BY songs.id;
.output stdout