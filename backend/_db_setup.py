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

    def _ensure_column(table_name: str, column_name: str, column_def: str) -> None:
        cur.execute(f"PRAGMA table_info({table_name})")
        existing = {row[1] for row in cur.fetchall()}
        if column_name in existing:
            return
        cur.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_def}")

    cur.execute(
        """
       CREATE TABLE IF NOT EXISTS "ratings" (
        rating_key INTEGER PRIMARY KEY AUTOINCREMENT,
        rating_type VARCHAR(50),
        rating_name VARCHAR(50),
        content_id INTEGER,
        content_info_artist VARCHAR(50),
        content_info_album VARCHAR(50), 
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

    _ensure_column("ratings", "image_url", "image_url TEXT")
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

    _ensure_column("bulletin", "created_by_user_id", "created_by_user_id INTEGER")
    _ensure_column("bulletin", "message", "message TEXT")
    _ensure_column("bulletin", "created_at", "created_at TEXT")
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
        CREATE TABLE IF NOT EXISTS rating_likes (
        rating_like_id INTEGER PRIMARY KEY AUTOINCREMENT,
        rating_key INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        created_at TEXT,
        UNIQUE(rating_key, user_id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS rating_category_votes (
        rating_key INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        category TEXT NOT NULL,
        vote INTEGER NOT NULL,
        updated_at TEXT,
        PRIMARY KEY (rating_key, user_id, category)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS rating_comments (
        comment_id INTEGER PRIMARY KEY AUTOINCREMENT,
        rating_key INTEGER NOT NULL,
        author_user_id INTEGER NOT NULL,
        message VARCHAR(500),
        created_at TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_rating_comments_rating
        ON rating_comments (rating_key)
        """
    )

    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_rating_category_votes_rating
        ON rating_category_votes (rating_key)
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS playlist_likes (
        playlist_like_id INTEGER PRIMARY KEY AUTOINCREMENT,
        playlist_key INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        created_at TEXT,
        UNIQUE(playlist_key, user_id)
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

    _ensure_column("playlist_songs", "playlist_key", "playlist_key INTEGER")
    cur.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_playlist_songs_unique
        ON playlist_songs (playlist_key, song_key)
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

    _ensure_column("song", "artist_link", "artist_link TEXT")
    _ensure_column("song", "song_link", "song_link TEXT")
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

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS profile_comments (
        comment_id INTEGER PRIMARY KEY AUTOINCREMENT,
        profile_user_id INTEGER,
        author_user_id INTEGER,
        message VARCHAR(500),
        created_at TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS alerts (
        alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        message TEXT NOT NULL,
        url TEXT,
        created_at TEXT,
        is_read INTEGER DEFAULT 0
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS activity (
        activity_id INTEGER PRIMARY KEY AUTOINCREMENT,
        actor_user_id INTEGER NOT NULL,
        actor_username TEXT NOT NULL,
        action TEXT NOT NULL,
        category TEXT,
        entity_type TEXT,
        entity_id INTEGER,
        entity_label TEXT,
        url TEXT,
        created_at TEXT,
        metadata TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS activity_dismissed (
        user_id INTEGER NOT NULL,
        activity_id INTEGER NOT NULL,
        dismissed_at TEXT,
        PRIMARY KEY (user_id, activity_id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS activity_clear (
        user_id INTEGER NOT NULL,
        category TEXT NOT NULL,
        cleared_at TEXT NOT NULL,
        PRIMARY KEY (user_id, category)
        )
        """
    )

    conn.commit()
    conn.close()
