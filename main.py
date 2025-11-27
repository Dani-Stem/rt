import sqlite3
from flask import Flask, render_template, request, redirect, url_for
from pathlib import Path

# -------------
# CONFIGURATION
# -------------

ROOT_DIR = Path(__file__).resolve().parent
DB_PATH = ROOT_DIR / "db.sqlite3"

app = Flask(__name__)


# --------
# DATABASE
# --------


# Database connection
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
        password VARCHAR(50),
        first_name VARCHAR(50),
        last_name VARCHAR(50),
        reviews VARCHAR(500),
        likes_key INTEGER,
        bulletin_key INTEGER,
        upvotes INTEGER,
        downvotes INTEGER,
        cred INTEGER,
        followers_key INTEGER,
        following_key INTEGER
        )
        """
    )
    conn.commit()
    conn.close()


# Database operations
def get_ratings():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT rating_key, rating_type, rating_name, lyrics_rating, beat_rating, flow_rating, melody_rating, cohesive_rating FROM ratings ORDER BY rating_key ASC"
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def get_rating_by_key(rating_key):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT rating_key, rating_type, rating_name, lyrics_rating, lyrics_reason, beat_rating, beat_reason, flow_rating, flow_reason, melody_rating, melody_reason, cohesive_rating, cohesive_reason FROM ratings WHERE rating_key = ?",
        (rating_key,),
    )
    row = cur.fetchone()
    conn.close()
    return row


def add_rating(
    rating_type: str,
    rating_name: str,
    lyrics_rating: int,
    lyrics_reason: str,
    beat_rating: int,
    beat_reason: str,
    flow_rating: int,
    flow_reason: str,
    melody_rating: int,
    melody_reason: str,
    cohesive_rating: int,
    cohesive_reason: str,
):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO ratings (rating_type, rating_name, lyrics_rating,lyrics_reason, beat_rating, beat_reason, flow_rating, flow_reason, melody_rating, melody_reason, cohesive_rating, cohesive_reason) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            rating_type,
            rating_name,
            lyrics_rating,
            lyrics_reason,
            beat_rating,
            beat_reason,
            flow_rating,
            flow_reason,
            melody_rating,
            melody_reason,
            cohesive_rating,
            cohesive_reason,
        ),
    )
    conn.commit()
    conn.close()


def update_rating(
    rating_key,
    rating_type,
    rating_name,
    lyrics_rating,
    lyrics_reason,
    beat_rating,
    beat_reason,
    flow_rating,
    flow_reason,
    melody_rating,
    melody_reason,
    cohesive_rating,
    cohesive_reason,
):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE ratings SET rating_type = ?, rating_name = ?, lyrics_rating = ?, lyrics_reason = ?, beat_rating = ?, beat_reason = ?, flow_rating = ?, flow_reason = ?, melody_rating = ?, melody_reason = ?, cohesive_rating = ?, cohesive_reason = ? WHERE rating_key = ?",
        (
            rating_type,
            rating_name,
            lyrics_rating,
            lyrics_reason,
            beat_rating,
            beat_reason,
            flow_rating,
            flow_reason,
            melody_rating,
            melody_reason,
            cohesive_rating,
            cohesive_reason,
            rating_key,
        ),
    )
    conn.commit()
    conn.close()


def delete_rating(rating_key):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM ratings WHERE rating_key = ?", (rating_key,))
    conn.commit()
    conn.close()


# ------
# ROUTES
# ------


# Home
@app.route("/")
def home():
    ratings = get_ratings()
    return render_template("index.html", ratings=ratings)

# Browse
@app.route("/browse")
def browse():
    ratings = get_ratings()
    return render_template("browse.html", ratings=ratings)

# Add
@app.route("/add", methods=["GET", "POST"])
def add():
    if request.method == "POST":
        rating_type = request.form.get("rating_type", "").strip()
        rating_name = request.form.get("rating_name", "").strip()
        lyrics_rating = request.form.get("lyrics", "").strip()
        lyrics_reason = request.form.get("lyrics_reason", "").strip()
        beat_rating = request.form.get("beat", "").strip()
        beat_reason = request.form.get("beat_reason", "").strip()
        flow_rating = request.form.get("flow", "").strip()
        flow_reason = request.form.get("flow_reason", "").strip()
        melody_rating = request.form.get("melody", "").strip()
        melody_reason = request.form.get("melody_reason", "").strip()
        cohesive_rating = request.form.get("cohesive", "").strip()
        cohesive_reason = request.form.get("cohesive_reason", "").strip()
        if rating_type:
            add_rating(
                rating_type,
                rating_name,
                lyrics_rating,
                lyrics_reason,
                beat_rating,
                beat_reason,
                flow_rating,
                flow_reason,
                melody_rating,
                melody_reason,
                cohesive_rating,
                cohesive_reason,
            )
        return redirect(url_for("home"))
    return render_template("add.html")


# Edit
@app.route("/edit/<int:rating_key>", methods=["GET", "POST"])
def edit(rating_key):
    if request.method == "POST":
        rating_type = request.form.get("rating_type", "").strip()
        rating_name = request.form.get("rating_name", "").strip()
        lyrics_rating = request.form.get("lyrics", "").strip()
        lyrics_reason = request.form.get("lyrics_reason", "").strip()
        beat_rating = request.form.get("beat", "").strip()
        beat_reason = request.form.get("beat_reason", "").strip()
        flow_rating = request.form.get("flow", "").strip()
        flow_reason = request.form.get("flow_reason", "").strip()
        melody_rating = request.form.get("melody", "").strip()
        melody_reason = request.form.get("melody_reason", "").strip()
        cohesive_rating = request.form.get("cohesive", "").strip()
        cohesive_reason = request.form.get("cohesive_reason", "").strip()
        if rating_type:
            update_rating(
                rating_key,
                rating_type,
                rating_name,
                lyrics_rating,
                lyrics_reason,
                beat_rating,
                beat_reason,
                flow_rating,
                flow_reason,
                melody_rating,
                melody_reason,
                cohesive_rating,
                cohesive_reason,
            )
        return redirect(url_for("home"))

    rating = get_rating_by_key(rating_key)
    if not rating:
        return redirect(url_for("home"))
    return render_template("edit.html", rating=rating)


# Delete
@app.route("/delete/<int:rating_key>", methods=["POST"])
def delete(rating_key):
    delete_rating(rating_key)
    return redirect(url_for("home"))


# -------
# STARTUP
# -------

# Starts the database
init_db()

# Runs the app
if __name__ == "__main__":
    app.run(host="localhost", port=8000, debug=True)
