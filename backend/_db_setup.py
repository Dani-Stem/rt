import sqlite3
from pathlib import Path

# Configuration
ROOT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = ROOT_DIR / "db.sqlite3"


# Connect to database
def get_db_connection():
    return sqlite3.connect(DB_PATH)


# Database setup
def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
       CREATE TABLE IF NOT EXISTS "ratings" (
        rating_key INTEGER PRIMARY KEY AUTOINCREMENT,
        id INTEGER,
        content VARCHAR(50),
        rating_type VARCHAR(50),
        rating_name VARCHAR(50), 
        lyrics_rating INTEGER,
        lyrics_reason  VARCHAR(500),
        beat_rating INTEGER,
        beat_reason  VARCHAR(500),
        flow_rating INTEGER,
        flow_reason VARCHAR(500),
        melody_rating INTEGER,
        melody_reason  VARCHAR(500),
        cohesive_rating INTEGER,
        cohesive_reason  VARCHAR(500),
        user VARCHAR(50),
        upvotes  INTEGER,
        downvotes INTEGER,
        challenged INTEGER,
        challenge_key INTEGER
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS "album" (
        album_key INTEGER PRIMARY KEY AUTOINCREMENT,
        album_title VARCHAR(50),
        artist_name VARCHAR(50),
        artist_key INTEGER, 
        release_date INTEGER, 
        genre_key INTEGER, 
        features_key INTEGER, 
        tag_key INTEGER, 
        avg_rating_lyrics INTEGER, 
        top_com_lyrics_key INTEGER, 
        avg_rating_beat INTEGER, 
        top_com_beat_key INTEGER, 
        avg_rating_df INTEGER, 
        top_com_df_key INTEGER, 
        avg_rating_melody INTEGER, 
        top_com_melody_key INTEGER, 
        avg_rating_cohesive INTEGER, 
        top_com_cohesive_key INTEGER, 
        uploaded_by VARCHAR(50),
        upvotes INTEGER, 
        downvotes INTEGER
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS "artist" (
        artist_key INTEGER PRIMARY KEY AUTOINCREMENT,
        artist_name VARCHAR(50),
        last_release VARCHAR(50),
        genre_key INTEGER,
        tag_key INTEGER,
        album_key INTEGER,
        track_list_key INTEGER,
        avg_rating_lyrics INTEGER,
        top_com_lyrics_key INTEGER,
        avg_rating_beat INTEGER,
        top_com_beat_key INTEGER,
        avg_rating_df INTEGER,
        top_com_df_key INTEGER,
        avg_rating_melody INTEGER,
        top_com_melody_key INTEGER,
        avg_rating_cohesive INTEGER,
        top_com_cohesive_key INTEGER,
        avg_rating_emoji INTEGER,
        avg_rating_emoji_2 INTEGER,
        avg_rating_emoji_3 INTEGER,
        uploaded_by VARCHAR(50),
        upvotes INTEGER,
        downvotes INTEGER
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS bulletin (
        bulletin_key INTEGER PRIMARY KEY AUTOINCREMENT,
        created_by VARCHAR(50),
        type VARCHAR(50)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS challenges (
        challenges_key INTEGER PRIMARY KEY AUTOINCREMENT,
        challenged_by VARCHAR(50),
        review_type VARCHAR(50),
        challenge_title VARCHAR(50),
        challenging VARCHAR(50),
        reason VARCHAR(500),
        bulletin_key INTEGER,
        review_key INTEGER
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS follow_info (
        follow_info_key INTEGER PRIMARY KEY AUTOINCREMENT,
        user_followed_key INTEGER,
        followed_by_user_key INTEGER,
        unfollowed INTEGER
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS likes_info (
        likes_info_key INTEGER PRIMARY KEY AUTOINCREMENT,
        liked_media_key INTEGER,
        liked_by VARCHAR(50),
        unliked INTEGER, 
        liked INTEGER 
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS playlist_info (
        playlist_key INTEGER PRIMARY KEY AUTOINCREMENT,
        created_by VARCHAR(50),
        playlist_title VARCHAR(50),
        playlist_description VARCHAR(50),
        songs_key INTEGER, 
        upvotes INTEGER,
        downvotes INTEGER
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS playlist_songs (
        playlist_songs_key INTEGER PRIMARY KEY AUTOINCREMENT,
        created_by VARCHAR(50),
        song_key INTEGER
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS song (
        song_key INTEGER PRIMARY KEY AUTOINCREMENT,
        song_title VARCHAR(50),
        artist_name VARCHAR(50),
        artist_key INTEGER,
        release_date INTEGER,
        genre_key INTEGER,
        features_key INTEGER,
        tag_key INTEGER,
        album_key INTEGER,
        avg_rating_lyrics INTEGER,
        top_com_lyrics_key INTEGER,
        avg_rating_beat INTEGER,
        top_com_beat_key INTEGER,
        avg_rating_df INTEGER,
        top_com_df_key INTEGER,
        avg_rating_melody INTEGER,
        top_com_melody_key INTEGER,
        avg_rating_cohesive INTEGER,
        top_com_cohesive_key INTEGER,
        uploaded_by VARCHAR(50),
        upvotes INTEGER,
        downvotes INTEGER
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS user_info (
        user_info_key INTEGER PRIMARY KEY AUTOINCREMENT,
        username VARCHAR(50),
        email VARCHAR(100),
        password VARCHAR(200),
        first_name VARCHAR(50),
        last_name VARCHAR(50),
        reviews VARCHAR(500),
        likes_key INTEGER,
        bulletin_key INTEGER,
        upvotes INTEGER,
        downvotes INTEGER,
        cred INTEGER,
        followers_key INTEGER,
        following_key INTEGER,
        profile_pic VARCHAR(255)
        )
        """
    )

    conn.commit()
    conn.close()
