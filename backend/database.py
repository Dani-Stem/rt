import sqlite3
from backend._db_setup import DB_PATH
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin


# Connect to database
def get_db_connection():
    return sqlite3.connect(DB_PATH)


# Get all ratings
def get_ratings():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT rating_key, rating_type, rating_name, lyrics_rating, beat_rating, flow_rating, melody_rating, cohesive_rating, user FROM ratings ORDER BY rating_key ASC"
    )
    rows = cur.fetchall()
    conn.close()
    return rows


# Get all artist
def get_artist():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT artist_key INTEGER PRIMARY KEY AUTOINCREMENT, artist_name, last_release, genre_key, tag_key, album_key, track_list_key, avg_rating_lyrics, top_com_lyrics_key, avg_rating_beat, top_com_beat_key, avg_rating_df, top_com_df_key, avg_rating_melody, top_com_melody_key, avg_rating_cohesive, top_com_cohesive_key, avg_rating_emoji, avg_rating_emoji_2, avg_rating_emoji_3, uploaded_by, upvotes, downvotes,favorites_key, picture, avg_rating  user FROM artist ORDER BY artist_key ASC"
    )
    rows = cur.fetchall()
    conn.close()
    return rows



# Get a rating by key
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


# Get rating owner
def get_rating_owner(rating_key):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT user FROM ratings WHERE rating_key = ?", (rating_key,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None


# Add a new rating
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
    user: str,
):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO ratings (rating_type, rating_name, lyrics_rating,lyrics_reason, beat_rating, beat_reason, flow_rating, flow_reason, melody_rating, melody_reason, cohesive_rating, cohesive_reason, user) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
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
            user,
        ),
    )
    conn.commit()
    conn.close()


# Update an existing rating
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


# Delete a rating
def delete_rating(rating_key):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM ratings WHERE rating_key = ?", (rating_key,))
    conn.commit()
    conn.close()


###############################################
# User
###############################################


# User class for Flask-Login
class User(UserMixin):
    def __init__(
        self,
        user_id,
        username,
        email,
        password_hash,
        first_name=None,
        last_name=None,
        reviews=None,
        likes_key=None,
        bulletin_key=None,
        upvotes=None,
        downvotes=None,
        cred=None,
        followers_key=None,
        following_key=None,
        profile_pic=None,
        about=None,
        favorites0=None,
        favorites1=None,
        favorites2=None,
        favorites3=None,
    ):
        self.id = user_id
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self.first_name = first_name
        self.last_name = last_name
        self.reviews = reviews
        self.likes_key = likes_key
        self.bulletin_key = bulletin_key
        self.upvotes = upvotes
        self.downvotes = downvotes
        self.profile_pic = profile_pic
        self.cred = cred
        self.followers_key = followers_key
        self.following_key = following_key
        self.about = about
        self.favorites0 = favorites0
        self.favorites1 = favorites1
        self.favorites2 = favorites2
        self.favorites3 = favorites3

    def get_id(self):
        return str(self.id)


# Get user by ID
def get_user_by_id(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT user_info_key, username, email, password, first_name, last_name, reviews, likes_key, bulletin_key, upvotes, downvotes, cred, followers_key, following_key, profile_pic, about, favorites0, favorites1, favorites2, favorites3 FROM user_info WHERE user_info_key = ?",
        (user_id,),
    )
    row = cur.fetchone()
    conn.close()
    return _row_to_user(row)


# Get user by username or email
def get_user_by_username_or_email(identifier):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT user_info_key, username, email, password, first_name, last_name, reviews, likes_key, bulletin_key, upvotes, downvotes, cred, followers_key, following_key, profile_pic, about, favorites0, favorites1, favorites2, favorites3 FROM user_info WHERE username = ? OR email = ?",
        (identifier, identifier),
    )
    row = cur.fetchone()
    conn.close()
    return _row_to_user(row)


# Converts DB row to User object
def _row_to_user(row):
    if not row:
        return None
    (
        user_id,
        username,
        email,
        password_hash,
        first_name,
        last_name,
        reviews,
        likes_key,
        bulletin_key,
        upvotes,
        downvotes,
        cred,
        followers_key,
        following_key,
        profile_pic,
        about,
        favorites0,
        favorites1,
        favorites2,
        favorites3,
    ) = row
    return User(
        user_id,
        username,
        email,
        password_hash,
        first_name,
        last_name,
        reviews,
        likes_key,
        bulletin_key,
        upvotes,
        downvotes,
        cred,
        followers_key,
        following_key,
        profile_pic,
        about,
        favorites0,
        favorites1,
        favorites2,
        favorites3
    )


# Check if username or email exists
def username_or_email_exists(username, email):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT 1 FROM user_info WHERE username = ? OR email = ? LIMIT 1",
        (username, email),
    )
    exists = cur.fetchone() is not None
    conn.close()
    return exists


# Create a new user
def create_user(username, email, password_plain):
    if username_or_email_exists(username, email):
        return None  # username or email is already taken
    password_hash = generate_password_hash(password_plain)
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO user_info (username, email, password, profile_pic) VALUES (?,?,?,?)",
        (username, email, password_hash, None),
    )
    conn.commit()
    user_id = cur.lastrowid
    conn.close()
    return get_user_by_id(user_id)


def verify_password(stored_hash, password_plain):
    return check_password_hash(stored_hash, password_plain)


# Update the user's profile info
def update_profile_info(user_id, username, about, favorites0):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE user_info SET username = ?, about = ?  WHERE user_info_key = ?",
        (username, about, favorites0, user_id),
    )
    conn.commit()
    conn.close()


# Update the user's profile picture
def update_profile_pic(user_id, profile_pic_path):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE user_info SET profile_pic = ? WHERE user_info_key = ?",
        (profile_pic_path, user_id),
    )
    conn.commit()
    conn.close()


# Get profile picture from database using the username
def get_profile_pic_by_username(username):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT profile_pic FROM user_info WHERE username = ?",
        (username,),
    )
    row = cur.fetchone()
    conn.close()
    return row[0] if row and row[0] else None


# Profile Comments
def get_profile_comments(profile_user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            profile_comments.comment_id,
            profile_comments.message,
            profile_comments.created_at,
            user_info.user_info_key,
            user_info.username,
            user_info.profile_pic
        FROM profile_comments
        JOIN user_info ON user_info.user_info_key = profile_comments.author_user_id
        WHERE profile_comments.profile_user_id = ?
        ORDER BY profile_comments.comment_id ASC
        """,
        (profile_user_id,),
    )
    rows = cur.fetchall()
    conn.close()
    comments = []
    for row in rows:
        (
            comment_id,
            message,
            created_at,
            author_user_id,
            username,
            profile_pic,
        ) = row
        comments.append(
            {
                "comment_id": comment_id,
                "message": message,
                "created_at": created_at,
                "author_user_id": author_user_id,
                "username": username,
                "profile_pic": profile_pic,
            }
        )
    return comments


def add_profile_comment(profile_user_id, author_user_id, message, created_at):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO profile_comments (profile_user_id, author_user_id, message, created_at)
        VALUES (?,?,?,?)
        """,
        (profile_user_id, author_user_id, message, created_at),
    )
    conn.commit()
    conn.close()


def update_profile_comment(comment_id, author_user_id, message):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE profile_comments
        SET message = ?
        WHERE comment_id = ? AND author_user_id = ?
        """,
        (message, comment_id, author_user_id),
    )
    conn.commit()
    conn.close()


def delete_profile_comment(comment_id, author_user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        DELETE FROM profile_comments
        WHERE comment_id = ? AND author_user_id = ?
        """,
        (comment_id, author_user_id),
    )
    conn.commit()
    conn.close()
