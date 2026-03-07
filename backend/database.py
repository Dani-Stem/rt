import sqlite3
import re
import json
from backend._db_setup import DB_PATH
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from datetime import datetime, timezone
from typing import Optional, Any


# Connect to database
def get_db_connection():
    return sqlite3.connect(DB_PATH)


###############################################
# Bulletin
###############################################


def add_bulletin_post(
    created_by_user_id: int,
    created_by: str,
    title: str,
    message: str,
    post_type: str = "praise",
):
    created_by = (created_by or "").strip()
    title = (title or "").strip()
    message = (message or "").strip()
    post_type = (post_type or "").strip()
    if not created_by or not message:
        return
    created_at = datetime.now(timezone.utc).isoformat()

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO bulletin (created_by_user_id, created_by, title, message, created_at, type)
        VALUES (?,?,?,?,?,?)
        """,
        (int(created_by_user_id), created_by, title or None, message, created_at, post_type),
    )
    bulletin_key = cur.lastrowid
    conn.commit()
    conn.close()
    return int(bulletin_key) if bulletin_key is not None else None


def get_bulletin_feed_for_user(user_id: int, limit: int = 15, offset: int = 0):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            bulletin_key,
            created_by,
            title,
            message,
            created_at,
            created_by_user_id,
            type
        FROM bulletin
        WHERE created_by_user_id = ?
           OR created_by_user_id IN (
                SELECT user_followed_key
                FROM follow_info
                WHERE followed_by_user_key = ?
                  AND (unfollowed IS NULL OR unfollowed = 0)
           )
        ORDER BY bulletin_key DESC
        LIMIT ?
        OFFSET ?
        """,
        (int(user_id), int(user_id), int(limit), int(offset)),
    )
    rows = cur.fetchall()
    conn.close()

    items = []
    for row in rows:
        bulletin_key, created_by, title, message, created_at, created_by_user_id, post_type = (
            row
        )
        items.append(
            {
                "bulletin_key": bulletin_key,
                "created_by": created_by,
                "title": title,
                "message": message,
                "created_at": created_at,
                "created_by_user_id": created_by_user_id,
                "type": post_type,
            }
        )
    return items


def count_bulletin_feed_for_user(user_id: int) -> int:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT COUNT(1)
        FROM bulletin
        WHERE created_by_user_id = ?
           OR created_by_user_id IN (
                SELECT user_followed_key
                FROM follow_info
                WHERE followed_by_user_key = ?
                  AND (unfollowed IS NULL OR unfollowed = 0)
           )
        """,
        (int(user_id), int(user_id)),
    )
    row = cur.fetchone()
    conn.close()
    try:
        return int(row[0]) if row and row[0] is not None else 0
    except (TypeError, ValueError):
        return 0


def get_bulletin_feed_sig_for_user(user_id: int) -> tuple[int, int]:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            COUNT(1) AS c,
            COALESCE(MAX(bulletin_key), 0) AS max_id
        FROM bulletin
        WHERE created_by_user_id = ?
           OR created_by_user_id IN (
                SELECT user_followed_key
                FROM follow_info
                WHERE followed_by_user_key = ?
                  AND (unfollowed IS NULL OR unfollowed = 0)
           )
        """,
        (int(user_id), int(user_id)),
    )
    row = cur.fetchone()
    conn.close()
    try:
        c = int(row[0]) if row and row[0] is not None else 0
    except (TypeError, ValueError):
        c = 0
    try:
        max_id = int(row[1]) if row and row[1] is not None else 0
    except (TypeError, ValueError):
        max_id = 0
    return (max(0, c), max(0, max_id))


def get_bulletin_post_for_user(user_id: int, bulletin_key: int) -> Optional[dict]:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            bulletin_key,
            created_by,
            title,
            message,
            created_at,
            created_by_user_id,
            type
        FROM bulletin
        WHERE bulletin_key = ?
          AND (
            created_by_user_id = ?
            OR created_by_user_id IN (
                SELECT user_followed_key
                FROM follow_info
                WHERE followed_by_user_key = ?
                  AND (unfollowed IS NULL OR unfollowed = 0)
            )
          )
        LIMIT 1
        """,
        (int(bulletin_key), int(user_id), int(user_id)),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None

    (
        bulletin_key,
        created_by,
        title,
        message,
        created_at,
        created_by_user_id,
        post_type,
    ) = row
    return {
        "bulletin_key": bulletin_key,
        "created_by": created_by,
        "title": title,
        "message": message,
        "created_at": created_at,
        "created_by_user_id": created_by_user_id,
        "type": post_type,
    }


def delete_bulletin_post(bulletin_key: int, user_id: int) -> bool:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        DELETE FROM bulletin
        WHERE bulletin_key = ? AND created_by_user_id = ?
        """,
        (int(bulletin_key), int(user_id)),
    )
    deleted = cur.rowcount or 0
    conn.commit()
    conn.close()
    return deleted > 0


###############################################
# Users
###############################################


def get_users(
    limit: int = 50,
    offset: int = 0,
    order: str = "newest",
) -> list[dict[str, Any]]:
    order = (order or "").strip().lower()
    if order not in {"az", "za", "newest", "oldest", "cred_high", "cred_low"}:
        order = "newest"

    order_clause = "username COLLATE NOCASE ASC"
    if order == "za":
        order_clause = "username COLLATE NOCASE DESC"
    elif order == "newest":
        order_clause = "user_info_key DESC"
    elif order == "oldest":
        order_clause = "user_info_key ASC"
    elif order == "cred_high":
        order_clause = "COALESCE(cred, 0) DESC, username COLLATE NOCASE ASC"
    elif order == "cred_low":
        order_clause = "COALESCE(cred, 0) ASC, username COLLATE NOCASE ASC"

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT
            user_info_key,
            username,
            profile_pic,
            cred
        FROM user_info
        ORDER BY {order_clause}
        LIMIT ?
        OFFSET ?
        """,
        (int(limit), int(offset)),
    )
    rows = cur.fetchall()
    conn.close()
    items: list[dict[str, Any]] = []
    for row in rows:
        user_id, username, profile_pic, cred = row
        items.append(
            {
                "user_id": user_id,
                "username": username,
                "profile_pic": profile_pic,
                "cred": cred,
            }
        )
    return items


def count_users() -> int:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(1) FROM user_info")
    row = cur.fetchone()
    conn.close()
    try:
        return int(row[0]) if row and row[0] is not None else 0
    except (TypeError, ValueError):
        return 0


def search_rated_subjects(
    *,
    kind: str,
    q: str,
    artist: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:

    kind = (kind or "").strip().lower()
    q = (q or "").strip()
    artist = (artist or "").strip()
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 10
    limit = max(1, min(50, limit))

    rating_type = {"song": "Song", "album": "Album", "artist": "Artist"}.get(kind)
    if not rating_type:
        return []

    name_like = f"%{q}%"
    artist_like = f"%{artist}%" if artist else "%"

    conn = get_db_connection()
    cur = conn.cursor()

    if kind == "artist":
        cur.execute(
            """
            SELECT
                rating_name,
                '' AS artist,
                COUNT(1) AS rating_count,
                MAX(mbid) AS mbid,
                MAX(image_url) AS image_url
            FROM ratings
            WHERE LOWER(TRIM(rating_type)) = LOWER(TRIM(?))
              AND (? = '' OR rating_name LIKE ? COLLATE NOCASE)
            GROUP BY LOWER(TRIM(rating_name))
            ORDER BY rating_count DESC, rating_name COLLATE NOCASE ASC
            LIMIT ?
            """,
            (rating_type, q, name_like, int(limit)),
        )
    else:
        cur.execute(
            """
            SELECT
                rating_name,
                COALESCE(content_info_artist, '') AS artist,
                COUNT(1) AS rating_count,
                MAX(mbid) AS mbid,
                MAX(image_url) AS image_url
            FROM ratings
            WHERE LOWER(TRIM(rating_type)) = LOWER(TRIM(?))
              AND (? = '' OR rating_name LIKE ? COLLATE NOCASE)
              AND (? = '' OR COALESCE(content_info_artist, '') LIKE ? COLLATE NOCASE)
            GROUP BY LOWER(TRIM(rating_name)), LOWER(TRIM(COALESCE(content_info_artist, '')))
            ORDER BY rating_count DESC, rating_name COLLATE NOCASE ASC
            LIMIT ?
            """,
            (rating_type, q, name_like, artist, artist_like, int(limit)),
        )

    rows = cur.fetchall()
    conn.close()

    out: list[dict[str, Any]] = []
    for name, a, rating_count, mbid, image_url in rows or []:
        out.append(
            {
                "name": name or "",
                "artist": a or "",
                "rating_count": int(rating_count or 0),
                "mbid": (mbid or "").strip() or None,
                "image_url": (image_url or "").strip() or None,
            }
        )
    return out


# Get all ratings
def get_ratings(limit: int = 500, offset: int = 0, order: str = "recent"):
    order = (order or "").strip().lower()
    if order not in {"recent", "oldest"}:
        order = "recent"
    order_clause = "DESC" if order == "recent" else "ASC"

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT rating_key, rating_type, rating_name, lyrics_rating, beat_rating, flow_rating, melody_rating, cohesive_rating, user, image_url
        FROM ratings
        ORDER BY rating_key {order_clause}
        LIMIT ?
        OFFSET ?
        """,
        (int(limit), int(offset)),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def get_ratings_by_type(
    rating_type: str,
    limit: int = 500,
    offset: int = 0,
    order: str = "recent",
):
    rating_type = (rating_type or "").strip()
    if not rating_type:
        return []

    order = (order or "").strip().lower()
    if order not in {"recent", "oldest"}:
        order = "recent"
    order_clause = "DESC" if order == "recent" else "ASC"

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT rating_key, rating_type, rating_name, lyrics_rating, beat_rating, flow_rating, melody_rating, cohesive_rating, user, image_url
        FROM ratings
        WHERE rating_type = ?
        ORDER BY rating_key {order_clause}
        LIMIT ?
        OFFSET ?
        """,
        (rating_type, int(limit), int(offset)),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


# Get a rating by key
def get_rating_by_key(rating_key):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT rating_key, rating_type, rating_name, lyrics_rating, lyrics_reason, beat_rating, beat_reason, flow_rating, flow_reason, melody_rating, melody_reason, cohesive_rating, cohesive_reason, mbid, mb_url, content_info_artist, image_url FROM ratings WHERE rating_key = ?",
        (rating_key,),
    )
    row = cur.fetchone()
    conn.close()
    return row


def _norm_key(s: str) -> str:
    return " ".join((s or "").strip().lower().split())


def get_users_who_rated_same_subject(
    *,
    exclude_rating_key: int,
    mbid: str | None,
    rating_type: str,
    rating_name: str,
    content_artist: str | None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:

    conn = get_db_connection()
    cur = conn.cursor()

    mbid = (mbid or "").strip()
    rating_type = (rating_type or "").strip()
    rating_name = (rating_name or "").strip()
    content_artist = (content_artist or "").strip()

    params: list[Any] = [int(exclude_rating_key)]
    where = ""
    if mbid:
        where = """
        WHERE r.rating_key != ?
          AND (
            r.mbid = ?
            OR (
              LOWER(TRIM(r.rating_type)) = LOWER(TRIM(?))
              AND LOWER(TRIM(r.rating_name)) = LOWER(TRIM(?))
              AND (
                LOWER(TRIM(COALESCE(r.content_info_artist, ''))) = LOWER(TRIM(?))
                OR TRIM(?) = ''
                OR TRIM(COALESCE(r.content_info_artist, '')) = ''
              )
            )
          )
        """
        params.extend([mbid, rating_type, rating_name, content_artist, content_artist])
    else:
        where = """
        WHERE r.rating_key != ?
          AND LOWER(TRIM(r.rating_type)) = LOWER(TRIM(?))
          AND LOWER(TRIM(r.rating_name)) = LOWER(TRIM(?))
          AND (
            LOWER(TRIM(COALESCE(r.content_info_artist, ''))) = LOWER(TRIM(?))
            OR TRIM(?) = ''
            OR TRIM(COALESCE(r.content_info_artist, '')) = ''
          )
        """
        params.extend([rating_type, rating_name, content_artist, content_artist])

    params.extend([int(limit), int(offset)])

    cur.execute(
        f"""
        SELECT
            ui.user_info_key,
            ui.username,
            ui.profile_pic,
            r.rating_key
        FROM ratings r
        JOIN user_info ui
            ON LOWER(TRIM(ui.username)) = LOWER(TRIM(r.user))
        {where}
        GROUP BY ui.user_info_key, ui.username, ui.profile_pic, r.rating_key
        ORDER BY ui.username COLLATE NOCASE ASC
        LIMIT ?
        OFFSET ?
        """,
        tuple(params),
    )
    rows = cur.fetchall()
    conn.close()

    out: list[dict[str, Any]] = []
    for user_id, username, profile_pic, rating_key in rows:
        out.append(
            {
                "user_id": int(user_id),
                "username": username,
                "profile_pic": profile_pic,
                "rating_key": int(rating_key),
            }
        )
    return out


def count_users_who_rated_same_subject(
    *,
    exclude_rating_key: int,
    mbid: str | None,
    rating_type: str,
    rating_name: str,
    content_artist: str | None,
) -> int:
    conn = get_db_connection()
    cur = conn.cursor()

    mbid = (mbid or "").strip()
    rating_type = (rating_type or "").strip()
    rating_name = (rating_name or "").strip()
    content_artist = (content_artist or "").strip()

    params: list[Any] = [int(exclude_rating_key)]
    if mbid:
        cur.execute(
            """
            SELECT COUNT(DISTINCT LOWER(TRIM(r.user)))
            FROM ratings r
            WHERE r.rating_key != ?
              AND (
                r.mbid = ?
                OR (
                  LOWER(TRIM(r.rating_type)) = LOWER(TRIM(?))
                  AND LOWER(TRIM(r.rating_name)) = LOWER(TRIM(?))
                  AND (
                    LOWER(TRIM(COALESCE(r.content_info_artist, ''))) = LOWER(TRIM(?))
                    OR TRIM(?) = ''
                    OR TRIM(COALESCE(r.content_info_artist, '')) = ''
                  )
                )
              )
            """,
            (
                int(exclude_rating_key),
                mbid,
                rating_type,
                rating_name,
                content_artist,
                content_artist,
            ),
        )
    else:
        cur.execute(
            """
            SELECT COUNT(DISTINCT LOWER(TRIM(r.user)))
            FROM ratings r
            WHERE r.rating_key != ?
              AND LOWER(TRIM(r.rating_type)) = LOWER(TRIM(?))
              AND LOWER(TRIM(r.rating_name)) = LOWER(TRIM(?))
              AND (
                LOWER(TRIM(COALESCE(r.content_info_artist, ''))) = LOWER(TRIM(?))
                OR TRIM(?) = ''
                OR TRIM(COALESCE(r.content_info_artist, '')) = ''
              )
            """,
            (
                int(exclude_rating_key),
                rating_type,
                rating_name,
                content_artist,
                content_artist,
            ),
        )

    row = cur.fetchone()
    conn.close()
    try:
        return int(row[0]) if row and row[0] is not None else 0
    except (TypeError, ValueError):
        return 0


def get_subject_activity_timeseries(
    *,
    action: str,
    mbid: str | None,
    rating_type: str,
    rating_name: str,
    content_artist: str | None,
    cutoff_iso: str | None = None,
    days: int = 7,
) -> list[dict[str, Any]]:

    action = (action or "").strip().lower()
    mbid = (mbid or "").strip()
    rating_type = (rating_type or "").strip()
    rating_name = (rating_name or "").strip()
    content_artist = (content_artist or "").strip()
    cutoff_iso = (cutoff_iso or "").strip() or None
    days = max(1, min(3650, int(days) if days is not None else 7))

    if not action or not rating_type or not rating_name:
        return []

    if days <= 1:
        group_expr = "SUBSTR(a.created_at, 1, 13)"
    elif days <= 90:
        group_expr = "SUBSTR(a.created_at, 1, 10)"
    else:
        group_expr = "SUBSTR(a.created_at, 1, 7)"

    conn = get_db_connection()
    cur = conn.cursor()

    params: list[Any] = []
    subj_where = ""
    if mbid:
        subj_where = """
            (r.mbid = ?)
            OR (
                LOWER(TRIM(r.rating_type)) = LOWER(TRIM(?))
                AND LOWER(TRIM(r.rating_name)) = LOWER(TRIM(?))
                AND (
                    LOWER(TRIM(COALESCE(r.content_info_artist, ''))) = LOWER(TRIM(?))
                    OR TRIM(?) = ''
                    OR TRIM(COALESCE(r.content_info_artist, '')) = ''
                )
            )
        """
        params.extend([mbid, rating_type, rating_name, content_artist, content_artist])
    else:
        subj_where = """
            LOWER(TRIM(r.rating_type)) = LOWER(TRIM(?))
            AND LOWER(TRIM(r.rating_name)) = LOWER(TRIM(?))
            AND (
                LOWER(TRIM(COALESCE(r.content_info_artist, ''))) = LOWER(TRIM(?))
                OR TRIM(?) = ''
                OR TRIM(COALESCE(r.content_info_artist, '')) = ''
            )
        """
        params.extend([rating_type, rating_name, content_artist, content_artist])

    cutoff_sql = ""
    if cutoff_iso:
        cutoff_sql = " AND a.created_at >= ? "
        params.append(cutoff_iso)

    cur.execute(
        f"""
        SELECT
            {group_expr} AS day,
            COUNT(1) AS event_count,
            COUNT(DISTINCT LOWER(TRIM(a.actor_username))) AS user_count
        FROM activity a
        JOIN ratings r
            ON r.rating_key = a.entity_id
        WHERE a.action = ?
          AND a.entity_type = 'rating'
          AND a.created_at IS NOT NULL
          AND ({subj_where})
          {cutoff_sql}
        GROUP BY day
        ORDER BY day ASC
        """,
        tuple([action] + params),
    )
    rows = cur.fetchall()
    conn.close()

    out: list[dict[str, Any]] = []
    for day, event_count, user_count in rows or []:
        out.append(
            {
                "day": str(day),
                "event_count": int(event_count or 0),
                "user_count": int(user_count or 0),
            }
        )
    return out


def get_subject_overall_summary(
    *,
    mbid: str | None,
    rating_type: str,
    rating_name: str,
    content_artist: str | None,
) -> dict[str, Any] | None:
    mbid = (mbid or "").strip()
    rating_type = (rating_type or "").strip()
    rating_name = (rating_name or "").strip()
    content_artist = (content_artist or "").strip()

    if not rating_type or not rating_name:
        return None

    params: list[Any] = []
    where = ""
    if mbid:
        where = """
        (
          mbid = ?
          OR (
            LOWER(TRIM(rating_type)) = LOWER(TRIM(?))
            AND LOWER(TRIM(rating_name)) = LOWER(TRIM(?))
            AND (
              LOWER(TRIM(COALESCE(content_info_artist, ''))) = LOWER(TRIM(?))
              OR TRIM(?) = ''
              OR TRIM(COALESCE(content_info_artist, '')) = ''
            )
          )
        )
        """
        params.extend([mbid, rating_type, rating_name, content_artist, content_artist])
    else:
        where = """
        LOWER(TRIM(rating_type)) = LOWER(TRIM(?))
        AND LOWER(TRIM(rating_name)) = LOWER(TRIM(?))
        AND (
          LOWER(TRIM(COALESCE(content_info_artist, ''))) = LOWER(TRIM(?))
          OR TRIM(?) = ''
          OR TRIM(COALESCE(content_info_artist, '')) = ''
        )
        """
        params.extend([rating_type, rating_name, content_artist, content_artist])

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT
          COUNT(1) AS rating_count,
          COUNT(DISTINCT LOWER(TRIM(user))) AS user_count,
          AVG(CAST(lyrics_rating AS REAL)) AS avg_lyrics,
          AVG(CAST(beat_rating AS REAL)) AS avg_beat,
          AVG(CAST(flow_rating AS REAL)) AS avg_flow,
          AVG(CAST(melody_rating AS REAL)) AS avg_melody,
          AVG(CAST(cohesive_rating AS REAL)) AS avg_cohesive,
          MAX(image_url) AS image_url
        FROM ratings
        WHERE {where}
        """,
        tuple(params),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None

    (
        rating_count,
        user_count,
        avg_lyrics,
        avg_beat,
        avg_flow,
        avg_melody,
        avg_cohesive,
        image_url,
    ) = row

    if not rating_count:
        return None

    def _round(v):
        try:
            return round(float(v), 2) if v is not None else None
        except (TypeError, ValueError):
            return None

    r_lyrics = _round(avg_lyrics)
    r_beat = _round(avg_beat)
    r_flow = _round(avg_flow)
    r_melody = _round(avg_melody)
    r_cohesive = _round(avg_cohesive)

    components = [v for v in (r_lyrics, r_beat, r_flow, r_melody, r_cohesive) if v is not None]
    overall_avg = round(sum(components) / len(components), 2) if components else None

    return {
        "rating_count": int(rating_count or 0),
        "user_count": int(user_count or 0),
        "overall_avg": overall_avg,
        "avg_lyrics": r_lyrics,
        "avg_beat": r_beat,
        "avg_flow": r_flow,
        "avg_melody": r_melody,
        "avg_cohesive": r_cohesive,
        "image_url": (image_url or "").strip() or None,
    }


# Get rating owner
def get_rating_owner(rating_key):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT user FROM ratings WHERE rating_key = ?", (rating_key,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None


def get_rating_comments(rating_key: int) -> list[dict[str, Any]]:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            rc.comment_id,
            rc.message,
            rc.created_at,
            ui.user_info_key,
            ui.username,
            ui.profile_pic
        FROM rating_comments rc
        JOIN user_info ui ON ui.user_info_key = rc.author_user_id
        WHERE rc.rating_key = ?
        ORDER BY rc.comment_id ASC
        """,
        (int(rating_key),),
    )
    rows = cur.fetchall()
    conn.close()

    comments: list[dict[str, Any]] = []
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
                "comment_id": int(comment_id),
                "message": message or "",
                "created_at": created_at,
                "author_user_id": int(author_user_id),
                "username": username,
                "profile_pic": profile_pic,
            }
        )
    return comments


def add_rating_comment(
    rating_key: int,
    author_user_id: int,
    message: str,
    created_at: str,
) -> None:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO rating_comments (rating_key, author_user_id, message, created_at)
        VALUES (?,?,?,?)
        """,
        (int(rating_key), int(author_user_id), message, created_at),
    )
    conn.commit()
    conn.close()


def get_rating_comment(comment_id: int) -> Optional[dict[str, Any]]:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT comment_id, rating_key, author_user_id, message, created_at
        FROM rating_comments
        WHERE comment_id = ?
        LIMIT 1
        """,
        (int(comment_id),),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "comment_id": int(row[0]),
        "rating_key": int(row[1]),
        "author_user_id": int(row[2]),
        "message": row[3] or "",
        "created_at": row[4],
    }


def update_rating_comment(comment_id: int, author_user_id: int, message: str) -> bool:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE rating_comments
        SET message = ?
        WHERE comment_id = ? AND author_user_id = ?
        """,
        (message, int(comment_id), int(author_user_id)),
    )
    updated = cur.rowcount or 0
    conn.commit()
    conn.close()
    return updated > 0


def delete_rating_comment(comment_id: int, author_user_id: int) -> bool:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        DELETE FROM rating_comments
        WHERE comment_id = ? AND author_user_id = ?
        """,
        (int(comment_id), int(author_user_id)),
    )
    deleted = cur.rowcount or 0
    conn.commit()
    conn.close()
    return deleted > 0


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
    image_url: str | None = None,
    mbid: str | None = None,
    mb_url: str | None = None,
    content_artist: str | None = None,
):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO ratings (rating_type, rating_name, lyrics_rating,lyrics_reason, beat_rating, beat_reason, flow_rating, flow_reason, melody_rating, melody_reason, cohesive_rating, cohesive_reason, user, image_url, mbid, mb_url, content_info_artist) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
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
            image_url,
            (mbid or "").strip() or None,
            (mb_url or "").strip() or None,
            ((content_artist or "").strip()[:50]) or None,
        ),
    )
    rating_key = cur.lastrowid
    conn.commit()
    conn.close()
    return int(rating_key) if rating_key is not None else None


###############################################
# Activity
###############################################


def add_activity(
    actor_user_id: int,
    actor_username: str,
    action: str,
    category: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    entity_label: Optional[str] = None,
    url: Optional[str] = None,
    created_at: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
):
    actor_username = (actor_username or "").strip()
    action = (action or "").strip()
    if not actor_user_id or not actor_username or not action:
        return

    created_at = created_at or datetime.now(timezone.utc).isoformat()
    category = (category or "").strip().lower() or None
    entity_type = (entity_type or "").strip().lower() or None
    entity_label = (entity_label or "").strip() or None
    url = (url or "").strip() or None
    metadata_json = json.dumps(metadata) if metadata else None

    if action.endswith("_view") and entity_type and entity_id is not None:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT 1
            FROM activity
            WHERE actor_user_id = ?
              AND action = ?
              AND entity_type = ?
              AND entity_id = ?
            LIMIT 1
            """,
            (int(actor_user_id), action, entity_type, int(entity_id)),
        )
        exists = cur.fetchone() is not None
        conn.close()
        if exists:
            return

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO activity (
            actor_user_id,
            actor_username,
            action,
            category,
            entity_type,
            entity_id,
            entity_label,
            url,
            created_at,
            metadata
        )
        VALUES (?,?,?,?,?,?,?,?,?,?)
        """,
        (
            int(actor_user_id),
            actor_username,
            action,
            category,
            entity_type,
            int(entity_id) if entity_id is not None else None,
            entity_label,
            url,
            created_at,
            metadata_json,
        ),
    )
    conn.commit()
    conn.close()


def activity_exists(
    *,
    actor_user_id: int,
    action: str,
    entity_type: str,
    entity_id: int,
) -> bool:
    action = (action or "").strip()
    entity_type = (entity_type or "").strip().lower()
    if not actor_user_id or not action or not entity_type:
        return False

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT 1
        FROM activity
        WHERE actor_user_id = ?
          AND action = ?
          AND entity_type = ?
          AND entity_id = ?
        LIMIT 1
        """,
        (int(actor_user_id), action, entity_type, int(entity_id)),
    )
    exists = cur.fetchone() is not None
    conn.close()
    return bool(exists)


def get_activity_feed_for_user(
    user_id: int,
    limit: int = 30,
    category: Optional[str] = None,
    offset: int = 0,
):
    category = (category or "").strip().lower() or None
    params: list[Any] = [int(user_id), int(user_id)]
    where_category = ""
    if category and category != "all":
        where_category = " AND (category = ?) "
        params.append(category)

    cleared_at = _get_activity_cleared_at(int(user_id), category)
    where_cleared = ""
    if cleared_at:
        where_cleared = " AND (created_at IS NOT NULL AND created_at > ?) "
        params.append(cleared_at)

    where_dismissed = " AND activity_id NOT IN (SELECT activity_id FROM activity_dismissed WHERE user_id = ?) "
    params.append(int(user_id))

    params.append(int(limit))
    params.append(int(offset))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT
            activity_id,
            actor_user_id,
            actor_username,
            action,
            category,
            entity_type,
            entity_id,
            entity_label,
            url,
            created_at,
            metadata
        FROM activity
        WHERE (
            actor_user_id = ?
            OR actor_user_id IN (
                SELECT user_followed_key
                FROM follow_info
                WHERE followed_by_user_key = ?
                  AND (unfollowed IS NULL OR unfollowed = 0)
            )
        )
        {where_category}
        {where_cleared}
        {where_dismissed}
        ORDER BY activity_id DESC
        LIMIT ?
        OFFSET ?
        """,
        tuple(params),
    )
    rows = cur.fetchall()
    conn.close()

    items = []
    for row in rows:
        (
            activity_id,
            actor_user_id,
            actor_username,
            action,
            category,
            entity_type,
            entity_id,
            entity_label,
            url,
            created_at,
            metadata_json,
        ) = row
        metadata = None
        if metadata_json:
            try:
                metadata = json.loads(metadata_json)
            except json.JSONDecodeError:
                metadata = None
        items.append(
            {
                "activity_id": activity_id,
                "actor_user_id": actor_user_id,
                "actor_username": actor_username,
                "action": action,
                "category": category,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "entity_label": entity_label,
                "url": url,
                "created_at": created_at,
                "metadata": metadata,
            }
        )
    return items


def count_activity_feed_for_user(user_id: int, category: Optional[str] = None) -> int:
    category = (category or "").strip().lower() or None
    params: list[Any] = [int(user_id), int(user_id)]
    where_category = ""
    if category and category != "all":
        where_category = " AND (category = ?) "
        params.append(category)

    cleared_at = _get_activity_cleared_at(int(user_id), category)
    where_cleared = ""
    if cleared_at:
        where_cleared = " AND (created_at IS NOT NULL AND created_at > ?) "
        params.append(cleared_at)

    where_dismissed = " AND activity_id NOT IN (SELECT activity_id FROM activity_dismissed WHERE user_id = ?) "
    params.append(int(user_id))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT COUNT(1)
        FROM activity
        WHERE (
            actor_user_id = ?
            OR actor_user_id IN (
                SELECT user_followed_key
                FROM follow_info
                WHERE followed_by_user_key = ?
                  AND (unfollowed IS NULL OR unfollowed = 0)
            )
        )
        {where_category}
        {where_cleared}
        {where_dismissed}
        """,
        tuple(params),
    )
    row = cur.fetchone()
    conn.close()
    try:
        return int(row[0]) if row and row[0] is not None else 0
    except (TypeError, ValueError):
        return 0


def get_activity_feed_sig_for_user(user_id: int, category: Optional[str] = None) -> tuple[int, int, Optional[str]]:

    category = (category or "").strip().lower() or None
    params: list[Any] = [int(user_id), int(user_id)]
    where_category = ""
    if category and category != "all":
        where_category = " AND (category = ?) "
        params.append(category)

    cleared_at = _get_activity_cleared_at(int(user_id), category)
    where_cleared = ""
    if cleared_at:
        where_cleared = " AND (created_at IS NOT NULL AND created_at > ?) "
        params.append(cleared_at)

    where_dismissed = " AND activity_id NOT IN (SELECT activity_id FROM activity_dismissed WHERE user_id = ?) "
    params.append(int(user_id))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT
            COUNT(1) AS c,
            COALESCE(MAX(activity_id), 0) AS max_id
        FROM activity
        WHERE (
            actor_user_id = ?
            OR actor_user_id IN (
                SELECT user_followed_key
                FROM follow_info
                WHERE followed_by_user_key = ?
                  AND (unfollowed IS NULL OR unfollowed = 0)
            )
        )
        {where_category}
        {where_cleared}
        {where_dismissed}
        """,
        tuple(params),
    )
    row = cur.fetchone()
    conn.close()
    try:
        c = int(row[0]) if row and row[0] is not None else 0
    except (TypeError, ValueError):
        c = 0
    try:
        max_id = int(row[1]) if row and row[1] is not None else 0
    except (TypeError, ValueError):
        max_id = 0
    return (max(0, c), max(0, max_id), cleared_at)


def dismiss_activity_for_user(user_id: int, activity_id: int) -> None:
    if not user_id or not activity_id:
        return
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT OR IGNORE INTO activity_dismissed (user_id, activity_id, dismissed_at)
        VALUES (?,?,?)
        """,
        (int(user_id), int(activity_id), datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()


def clear_activity_for_user(user_id: int, category: Optional[str] = None) -> None:
    if not user_id:
        return
    category_key = (category or "").strip().lower() or "all"
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT OR REPLACE INTO activity_clear (user_id, category, cleared_at)
        VALUES (?,?,?)
        """,
        (int(user_id), category_key, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()


def _get_activity_cleared_at(
    user_id: int, category: Optional[str] = None
) -> Optional[str]:

    category_key = (category or "").strip().lower() or "all"
    keys = ["all"] if category_key == "all" else ["all", category_key]

    conn = get_db_connection()
    cur = conn.cursor()
    placeholders = ",".join(["?"] * len(keys))
    cur.execute(
        f"""
        SELECT category, cleared_at
        FROM activity_clear
        WHERE user_id = ?
          AND category IN ({placeholders})
        """,
        (int(user_id), *keys),
    )
    rows = cur.fetchall()
    conn.close()

    cleared = None
    for _cat, ts in rows or []:
        if not ts:
            continue
        if cleared is None or ts > cleared:
            cleared = ts
    return cleared


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
    image_url=None,
    mbid: str | None = None,
    mb_url: str | None = None,
    content_artist: str | None = None,
):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE ratings SET rating_type = ?, rating_name = ?, lyrics_rating = ?, lyrics_reason = ?, beat_rating = ?, beat_reason = ?, flow_rating = ?, flow_reason = ?, melody_rating = ?, melody_reason = ?, cohesive_rating = ?, cohesive_reason = ?, image_url = ?, mbid = ?, mb_url = ?, content_info_artist = ? WHERE rating_key = ?",
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
            image_url,
            (mbid or "").strip() or None,
            (mb_url or "").strip() or None,
            ((content_artist or "").strip()[:50]) or None,
            rating_key,
        ),
    )
    conn.commit()
    conn.close()


# Delete a rating
def delete_rating(rating_key):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM rating_comments WHERE rating_key = ?", (rating_key,))
    cur.execute("DELETE FROM rating_likes WHERE rating_key = ?", (rating_key,))
    cur.execute("DELETE FROM rating_category_votes WHERE rating_key = ?", (rating_key,))
    cur.execute("DELETE FROM ratings WHERE rating_key = ?", (rating_key,))
    conn.commit()
    conn.close()


###############################################
# Rating Likes
###############################################


def is_rating_liked_by_user(rating_key: int, user_id: int) -> bool:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT 1
        FROM rating_likes
        WHERE rating_key = ? AND user_id = ?
        LIMIT 1
        """,
        (int(rating_key), int(user_id)),
    )
    row = cur.fetchone()
    conn.close()
    return bool(row)


def get_rating_like_count(rating_key: int) -> int:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT COUNT(*)
        FROM rating_likes
        WHERE rating_key = ?
        """,
        (int(rating_key),),
    )
    row = cur.fetchone()
    conn.close()
    return int(row[0]) if row and row[0] is not None else 0


def toggle_rating_like(rating_key: int, user_id: int) -> bool:
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT rating_like_id
        FROM rating_likes
        WHERE rating_key = ? AND user_id = ?
        LIMIT 1
        """,
        (int(rating_key), int(user_id)),
    )
    row = cur.fetchone()
    if row:
        cur.execute(
            "DELETE FROM rating_likes WHERE rating_like_id = ?",
            (int(row[0]),),
        )
        conn.commit()
        conn.close()
        return False

    created_at = datetime.now(timezone.utc).isoformat()
    cur.execute(
        """
        INSERT OR IGNORE INTO rating_likes (rating_key, user_id, created_at)
        VALUES (?,?,?)
        """,
        (int(rating_key), int(user_id), created_at),
    )
    conn.commit()
    conn.close()
    return True


def get_liked_ratings_for_user(user_id: int, limit: int = 200, offset: int = 0):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            r.rating_key,
            r.rating_type,
            r.rating_name,
            r.lyrics_rating,
            r.beat_rating,
            r.flow_rating,
            r.melody_rating,
            r.cohesive_rating,
            r.user,
            r.image_url
        FROM rating_likes rl
        JOIN ratings r
            ON r.rating_key = rl.rating_key
        WHERE rl.user_id = ?
        ORDER BY rl.rating_like_id DESC
        LIMIT ?
        OFFSET ?
        """,
        (int(user_id), int(limit), int(offset)),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def get_upvoted_ratings_for_user(user_id: int, limit: int = 200, offset: int = 0):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            r.rating_key,
            r.rating_type,
            r.rating_name,
            r.lyrics_rating,
            r.beat_rating,
            r.flow_rating,
            r.melody_rating,
            r.cohesive_rating,
            r.user,
            r.lyrics_reason,
            r.beat_reason,
            r.flow_reason,
            r.melody_reason,
            r.cohesive_reason
        FROM rating_category_votes rcv
        JOIN ratings r
            ON r.rating_key = rcv.rating_key
        WHERE rcv.user_id = ?
          AND rcv.vote = 1
        GROUP BY r.rating_key
        ORDER BY
            (MAX(rcv.updated_at) IS NULL) ASC,
            MAX(rcv.updated_at) DESC,
            r.rating_key DESC
        LIMIT ?
        OFFSET ?
        """,
        (int(user_id), int(limit), int(offset)),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def get_upvoted_categories_for_user_ratings(
    user_id: int,
    rating_keys: list[int],
) -> dict[int, list[str]]:
    if not rating_keys:
        return {}

    keys = [int(k) for k in rating_keys]
    placeholders = ",".join(["?"] * len(keys))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT rating_key, category
        FROM rating_category_votes
        WHERE user_id = ?
          AND vote = 1
          AND rating_key IN ({placeholders})
        ORDER BY
            (updated_at IS NULL) ASC,
            updated_at DESC,
            category ASC
        """,
        tuple([int(user_id)] + keys),
    )
    rows = cur.fetchall()
    conn.close()

    result: dict[int, list[str]] = {}
    for rating_key, category in rows:
        rk = int(rating_key)
        cat = (category or "").strip()
        if not cat:
            continue
        result.setdefault(rk, [])
        if cat not in result[rk]:
            result[rk].append(cat)

    return result


###############################################
# Rating Category Votes
###############################################


def set_rating_category_vote(
    rating_key: int,
    user_id: int,
    category: str,
    vote: int,
) -> None:

    category = (category or "").strip()
    if not category:
        return

    try:
        vote_int = int(vote)
    except (TypeError, ValueError):
        return

    if vote_int not in (-1, 0, 1):
        return

    conn = get_db_connection()
    cur = conn.cursor()

    if vote_int == 0:
        cur.execute(
            """
            DELETE FROM rating_category_votes
            WHERE rating_key = ? AND user_id = ? AND category = ?
            """,
            (int(rating_key), int(user_id), category),
        )
        conn.commit()
        conn.close()
        return

    updated_at = datetime.now(timezone.utc).isoformat()

    try:
        cur.execute(
            """
            INSERT INTO rating_category_votes (rating_key, user_id, category, vote, updated_at)
            VALUES (?,?,?,?,?)
            ON CONFLICT(rating_key, user_id, category)
            DO UPDATE SET vote = excluded.vote, updated_at = excluded.updated_at
            """,
            (int(rating_key), int(user_id), category, int(vote_int), updated_at),
        )
    except sqlite3.OperationalError:
        cur.execute(
            """
            UPDATE rating_category_votes
            SET vote = ?, updated_at = ?
            WHERE rating_key = ? AND user_id = ? AND category = ?
            """,
            (int(vote_int), updated_at, int(rating_key), int(user_id), category),
        )
        if (cur.rowcount or 0) == 0:
            cur.execute(
                """
                INSERT INTO rating_category_votes (rating_key, user_id, category, vote, updated_at)
                VALUES (?,?,?,?,?)
                """,
                (int(rating_key), int(user_id), category, int(vote_int), updated_at),
            )

    conn.commit()
    conn.close()


def get_rating_category_votes_summary(rating_key: int) -> dict[str, dict[str, int]]:

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            category,
            COALESCE(SUM(vote), 0) AS score,
            COALESCE(SUM(CASE WHEN vote = 1 THEN 1 ELSE 0 END), 0) AS up,
            COALESCE(SUM(CASE WHEN vote = -1 THEN 1 ELSE 0 END), 0) AS down
        FROM rating_category_votes
        WHERE rating_key = ?
        GROUP BY category
        """,
        (int(rating_key),),
    )
    rows = cur.fetchall()
    conn.close()

    out: dict[str, dict[str, int]] = {}
    for category, score, up, down in rows:
        out[str(category)] = {
            "score": int(score) if score is not None else 0,
            "up": int(up) if up is not None else 0,
            "down": int(down) if down is not None else 0,
        }
    return out


def get_user_rating_category_votes(rating_key: int, user_id: int) -> dict[str, int]:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT category, vote
        FROM rating_category_votes
        WHERE rating_key = ? AND user_id = ?
        """,
        (int(rating_key), int(user_id)),
    )
    rows = cur.fetchall()
    conn.close()

    out: dict[str, int] = {}
    for category, vote in rows:
        try:
            out[str(category)] = int(vote)
        except (TypeError, ValueError):
            continue
    return out


def get_category_vote_totals_for_ratings(
    rating_keys: list[int],
) -> dict[int, dict[str, int]]:

    keys = [int(k) for k in (rating_keys or []) if k is not None]
    if not keys:
        return {}
    keys = sorted(set(keys))
    placeholders = ",".join(["?"] * len(keys))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT
          rating_key,
          COALESCE(SUM(CASE WHEN vote = 1 THEN 1 ELSE 0 END), 0) AS up,
          COALESCE(SUM(CASE WHEN vote = -1 THEN 1 ELSE 0 END), 0) AS down
        FROM rating_category_votes
        WHERE rating_key IN ({placeholders})
        GROUP BY rating_key
        """,
        tuple(keys),
    )
    rows = cur.fetchall()
    conn.close()

    out: dict[int, dict[str, int]] = {}
    for rating_key, up, down in rows or []:
        try:
            rk = int(rating_key)
        except (TypeError, ValueError):
            continue
        try:
            up_i = int(up or 0)
        except (TypeError, ValueError):
            up_i = 0
        try:
            down_i = int(down or 0)
        except (TypeError, ValueError):
            down_i = 0
        out[rk] = {"up": max(0, up_i), "down": max(0, down_i)}
    return out


###############################################
# Rating Reactions
###############################################


def get_rating_reactions_summary(rating_key: int) -> dict[str, list[dict[str, Any]]]:

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT category, emoji, COUNT(1) AS c
        FROM rating_reactions
        WHERE rating_key = ?
        GROUP BY category, emoji
        ORDER BY category ASC, c DESC, emoji ASC
        """,
        (int(rating_key),),
    )
    rows = cur.fetchall()
    conn.close()

    out: dict[str, list[dict[str, Any]]] = {}
    for category, emoji, c in rows or []:
        cat = str(category or "")
        em = str(emoji or "")
        if not cat or not em:
            continue
        out.setdefault(cat, []).append({"emoji": em, "count": int(c or 0)})
    return out


def get_user_rating_reactions(rating_key: int, user_id: int) -> dict[str, set[str]]:

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT category, emoji
        FROM rating_reactions
        WHERE rating_key = ? AND user_id = ?
        """,
        (int(rating_key), int(user_id)),
    )
    rows = cur.fetchall()
    conn.close()

    out: dict[str, set[str]] = {}
    for category, emoji in rows or []:
        cat = str(category or "")
        em = str(emoji or "")
        if not cat or not em:
            continue
        out.setdefault(cat, set()).add(em)
    return out


def toggle_rating_reaction(
    rating_key: int, user_id: int, *, category: str, emoji: str
) -> bool:

    category = (category or "").strip()
    emoji = (emoji or "").strip()
    if not category or not emoji:
        return False

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT reaction_id
        FROM rating_reactions
        WHERE rating_key = ? AND user_id = ? AND category = ? AND emoji = ?
        LIMIT 1
        """,
        (int(rating_key), int(user_id), category, emoji),
    )
    row = cur.fetchone()

    if row:
        cur.execute(
            "DELETE FROM rating_reactions WHERE reaction_id = ?",
            (int(row[0]),),
        )
        conn.commit()
        conn.close()
        return False

    created_at = datetime.now(timezone.utc).isoformat()
    cur.execute(
        """
        INSERT OR IGNORE INTO rating_reactions (rating_key, user_id, category, emoji, created_at)
        VALUES (?,?,?,?,?)
        """,
        (int(rating_key), int(user_id), category, emoji, created_at),
    )
    conn.commit()
    conn.close()
    return True


def get_reaction_counts_for_ratings(
    rating_keys: list[int],
) -> dict[int, list[tuple[str, int]]]:

    keys = [int(k) for k in (rating_keys or []) if k is not None]
    if not keys:
        return {}

    keys = sorted(set(keys))
    placeholders = ",".join(["?"] * len(keys))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT rating_key, emoji, COUNT(1) AS c
        FROM rating_reactions
        WHERE rating_key IN ({placeholders})
        GROUP BY rating_key, emoji
        """,
        tuple(keys),
    )
    rows = cur.fetchall()
    conn.close()

    out: dict[int, list[tuple[str, int]]] = {}
    for rating_key, emoji, c in rows or []:
        try:
            rk = int(rating_key)
        except (TypeError, ValueError):
            continue
        em = str(emoji or "").strip()
        if not em:
            continue
        try:
            cnt = int(c or 0)
        except (TypeError, ValueError):
            cnt = 0
        out.setdefault(rk, []).append((em, cnt))
    return out


###############################################
# Playlist Favorites
###############################################


def is_playlist_favorited_by_user(playlist_key: int, user_id: int) -> bool:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT 1
        FROM playlist_likes
        WHERE playlist_key = ? AND user_id = ?
        LIMIT 1
        """,
        (int(playlist_key), int(user_id)),
    )
    row = cur.fetchone()
    conn.close()
    return bool(row)


def toggle_playlist_favorite(playlist_key: int, user_id: int) -> bool:
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT playlist_like_id
        FROM playlist_likes
        WHERE playlist_key = ? AND user_id = ?
        LIMIT 1
        """,
        (int(playlist_key), int(user_id)),
    )
    row = cur.fetchone()
    if row:
        cur.execute(
            "DELETE FROM playlist_likes WHERE playlist_like_id = ?",
            (int(row[0]),),
        )
        conn.commit()
        conn.close()
        return False

    created_at = datetime.now(timezone.utc).isoformat()
    cur.execute(
        """
        INSERT OR IGNORE INTO playlist_likes (playlist_key, user_id, created_at)
        VALUES (?,?,?)
        """,
        (int(playlist_key), int(user_id), created_at),
    )
    conn.commit()
    conn.close()
    return True


def get_favorited_playlists_for_user(user_id: int, limit: int = 200, offset: int = 0):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            p.playlist_key,
            p.created_by,
            p.playlist_title,
            p.playlist_description
        FROM playlist_likes pl
        JOIN playlist_info p
            ON p.playlist_key = pl.playlist_key
        WHERE pl.user_id = ?
        ORDER BY pl.playlist_like_id DESC
        LIMIT ?
        OFFSET ?
        """,
        (int(user_id), int(limit), int(offset)),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


###############################################
# Playlists
###############################################


def add_playlist(created_by: str, title: str, description: str | None = None):
    created_by = (created_by or "").strip()
    title = (title or "").strip()
    description = (description or "").strip()

    if not created_by or not title:
        return None

    title = title[:50]
    description = description[:50]

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO playlist_info (
            created_by,
            playlist_title,
            playlist_description,
            songs_key,
            upvotes,
            downvotes
        )
        VALUES (?,?,?,?,?,?)
        """,
        (
            created_by,
            title,
            description or None,
            None,
            0,
            0,
        ),
    )
    playlist_key = cur.lastrowid
    conn.commit()
    conn.close()
    return int(playlist_key) if playlist_key is not None else None


def get_playlists_by_creator(created_by: str, limit: int = 60, offset: int = 0):
    created_by = (created_by or "").strip()
    if not created_by:
        return []
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT playlist_key, created_by, playlist_title, playlist_description
        FROM playlist_info
        WHERE created_by = ?
        ORDER BY playlist_key DESC
        LIMIT ?
        OFFSET ?
        """,
        (created_by, int(limit), int(offset)),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def get_playlists_by_following(user_id: int, limit: int = 200, offset: int = 0):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
                SELECT p.playlist_key, p.created_by, p.playlist_title, p.playlist_description
                FROM playlist_info p
                JOIN user_info u
                    ON u.username = p.created_by
                WHERE u.user_info_key IN (
                        SELECT user_followed_key
                        FROM follow_info
                        WHERE followed_by_user_key = ?
                            AND (unfollowed IS NULL OR unfollowed = 0)
                )
                ORDER BY p.playlist_key DESC
                LIMIT ?
                OFFSET ?
                """,
        (int(user_id), int(limit), int(offset)),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def get_playlist_by_key(playlist_key: int):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT playlist_key, created_by, playlist_title, playlist_description
        FROM playlist_info
        WHERE playlist_key = ?
        """,
        (int(playlist_key),),
    )
    row = cur.fetchone()
    conn.close()
    return row


def remove_song_from_playlist(playlist_key: int, song_key: int) -> bool:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        DELETE FROM playlist_songs
        WHERE playlist_key = ? AND song_key = ?
        """,
        (int(playlist_key), int(song_key)),
    )
    conn.commit()
    removed = cur.rowcount
    conn.close()
    return bool(removed)


def delete_playlist(playlist_key: int) -> bool:
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM playlist_songs WHERE playlist_key = ?",
        (int(playlist_key),),
    )
    cur.execute(
        "DELETE FROM playlist_likes WHERE playlist_key = ?",
        (int(playlist_key),),
    )
    cur.execute(
        "DELETE FROM playlist_info WHERE playlist_key = ?",
        (int(playlist_key),),
    )
    conn.commit()
    deleted = cur.rowcount
    conn.close()
    return bool(deleted)


def get_playlist_songs(playlist_key: int, limit: int = 500):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT s.song_key, s.song_title, s.artist_name, s.artist_link, s.song_link
        FROM playlist_songs ps
        JOIN song s ON s.song_key = ps.song_key
        WHERE ps.playlist_key = ?
        ORDER BY ps.playlist_songs_key DESC
        LIMIT ?
        """,
        (int(playlist_key), int(limit)),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def add_song_to_playlist(playlist_key: int, created_by: str, song_key: int):
    created_by = (created_by or "").strip()
    if not created_by:
        return False

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT song_key FROM song WHERE song_key = ?",
        (int(song_key),),
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        return False

    try:
        cur.execute(
            """
            INSERT INTO playlist_songs (playlist_key, created_by, song_key)
            VALUES (?,?,?)
            """,
            (int(playlist_key), created_by, int(song_key)),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return False

    conn.close()
    return True


def add_song(
    title: str,
    artist_name: str | None = None,
    artist_link: str | None = None,
    song_link: str | None = None,
    uploaded_by: str | None = None,
):
    title = (title or "").strip()
    artist_name = (artist_name or "").strip()
    artist_link = (artist_link or "").strip()
    song_link = (song_link or "").strip()
    uploaded_by = (uploaded_by or "").strip()
    if not title:
        return None

    title = title[:50]
    artist_name = artist_name[:50]
    artist_link = artist_link[:500]
    song_link = song_link[:500]
    uploaded_by = uploaded_by[:50]

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO song (song_title, artist_name, artist_link, song_link, uploaded_by, upvotes, downvotes)
        VALUES (?,?,?,?,?,?,?)
        """,
        (
            title,
            artist_name or None,
            artist_link or None,
            song_link or None,
            uploaded_by or None,
            0,
            0,
        ),
    )
    song_key = cur.lastrowid
    conn.commit()
    conn.close()
    return int(song_key) if song_key is not None else None


def search_songs(query: str, limit: int = 30):
    query = (query or "").strip()
    if not query:
        return []
    conn = get_db_connection()
    cur = conn.cursor()
    pattern = _search_pattern(query)
    cur.execute(
        """
        SELECT song_key, song_title, artist_name, artist_link, song_link
        FROM song
        WHERE song_title LIKE ? COLLATE NOCASE
           OR artist_name LIKE ? COLLATE NOCASE
        ORDER BY song_key DESC
        LIMIT ?
        """,
        (pattern, pattern, int(limit)),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


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

    def get_id(self):
        return str(self.id)


# Get user by ID
def get_user_by_id(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT user_info_key, username, email, password, first_name, last_name, reviews, likes_key, bulletin_key, upvotes, downvotes, cred, followers_key, following_key, profile_pic, about FROM user_info WHERE user_info_key = ?",
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
        "SELECT user_info_key, username, email, password, first_name, last_name, reviews, likes_key, bulletin_key, upvotes, downvotes, cred, followers_key, following_key, profile_pic, about FROM user_info WHERE username = ? OR email = ?",
        (identifier, identifier),
    )
    row = cur.fetchone()
    conn.close()
    return _row_to_user(row)


def get_user_by_username(username):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT user_info_key, username, email, password, first_name, last_name, reviews, likes_key, bulletin_key, upvotes, downvotes, cred, followers_key, following_key, profile_pic, about FROM user_info WHERE username = ?",
        (username,),
    )
    row = cur.fetchone()
    conn.close()
    return _row_to_user(row)


def _search_pattern(query):
    tokens = [token for token in re.split(r"[\s\W_]+", query.strip()) if token]
    return "%" + "%".join(tokens) + "%" if tokens else ""


def search_users_by_username(query, limit: int = 20, offset: int = 0):
    query = (query or "").strip()
    if not query:
        return []
    conn = get_db_connection()
    cur = conn.cursor()
    pattern = _search_pattern(query)
    cur.execute(
        """
        SELECT user_info_key, username, profile_pic
        FROM user_info
        WHERE username LIKE ? COLLATE NOCASE
        ORDER BY username COLLATE NOCASE ASC
        LIMIT ?
        OFFSET ?
        """,
        (pattern, int(limit), int(offset)),
    )
    rows = cur.fetchall()
    conn.close()
    return [
        {"user_id": row[0], "username": row[1], "profile_pic": row[2]} for row in rows
    ]


def search_ratings(query, limit: int = 20, offset: int = 0):
    query = (query or "").strip()
    if not query:
        return []
    conn = get_db_connection()
    cur = conn.cursor()
    pattern = _search_pattern(query)
    cur.execute(
        """
        SELECT rating_key, rating_type, rating_name, lyrics_rating, beat_rating, flow_rating, melody_rating, cohesive_rating, user, image_url
        FROM ratings
        WHERE rating_name LIKE ? COLLATE NOCASE OR rating_type LIKE ? COLLATE NOCASE OR user LIKE ? COLLATE NOCASE
        ORDER BY rating_key DESC
        LIMIT ?
        OFFSET ?
        """,
        (pattern, pattern, pattern, int(limit), int(offset)),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def search_playlists(query, limit: int = 20, offset: int = 0):
    query = (query or "").strip()
    if not query:
        return []

    conn = get_db_connection()
    cur = conn.cursor()
    pattern = _search_pattern(query)
    cur.execute(
        """
        SELECT playlist_key, created_by, playlist_title, playlist_description
        FROM playlist_info
        WHERE playlist_title LIKE ? COLLATE NOCASE
           OR playlist_description LIKE ? COLLATE NOCASE
           OR created_by LIKE ? COLLATE NOCASE
        ORDER BY playlist_key DESC
        LIMIT ?
          OFFSET ?
        """,
        (pattern, pattern, pattern, int(limit), int(offset)),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def search_song_ratings(query, limit=20):
    query = (query or "").strip()
    if not query:
        return []
    conn = get_db_connection()
    cur = conn.cursor()
    pattern = _search_pattern(query)
    cur.execute(
        """
                SELECT rating_key, rating_type, rating_name, lyrics_rating, beat_rating, flow_rating, melody_rating, cohesive_rating, user, image_url
        FROM ratings
        WHERE rating_type = 'Song'
          AND rating_name LIKE ? COLLATE NOCASE
        ORDER BY rating_key DESC
        LIMIT ?
        """,
        (pattern, int(limit)),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def get_ratings_by_user(username):
    if not username:
        return []
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT rating_key, rating_type, rating_name, lyrics_rating, beat_rating, flow_rating, melody_rating, cohesive_rating, user, image_url
        FROM ratings
        WHERE user = ? COLLATE NOCASE
        ORDER BY rating_key DESC
        """,
        (username,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def get_ratings_by_user_paginated(username: str, limit: int = 60, offset: int = 0):
    username = (username or "").strip()
    if not username:
        return []
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT rating_key, rating_type, rating_name, lyrics_rating, beat_rating, flow_rating, melody_rating, cohesive_rating, user, image_url
        FROM ratings
        WHERE user = ? COLLATE NOCASE
        ORDER BY rating_key DESC
        LIMIT ?
        OFFSET ?
        """,
        (username, int(limit), int(offset)),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


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
def update_profile_info(user_id, username, about):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT username FROM user_info WHERE user_info_key = ?", (user_id,))
    row = cur.fetchone()
    previous_username = row[0] if row else None
    cur.execute(
        "UPDATE user_info SET username = ?, about = ?  WHERE user_info_key = ?",
        (username, about, user_id),
    )
    if previous_username and previous_username != username:
        cur.execute(
            "UPDATE ratings SET user = ? WHERE user = ? COLLATE NOCASE",
            (username, previous_username),
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


###############################################
# Alerts
###############################################


def create_alert(
    user_id: int,
    message: str,
    url: Optional[str] = None,
    created_at: Optional[str] = None,
):
    if not user_id or not message:
        return
    created_at = created_at or datetime.now(timezone.utc).isoformat()
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO alerts (user_id, message, url, created_at, is_read)
        VALUES (?,?,?,?,0)
        """,
        (user_id, message, url, created_at),
    )
    conn.commit()
    conn.close()


def get_alerts_for_user(
    user_id: int,
    limit: int = 10,
    include_read: bool = False,
    offset: int = 0,
):
    conn = get_db_connection()
    cur = conn.cursor()
    if include_read:
        cur.execute(
            """
            SELECT alert_id, message, url, created_at, is_read
            FROM alerts
            WHERE user_id = ?
            ORDER BY alert_id DESC
            LIMIT ?
            OFFSET ?
            """,
            (int(user_id), int(limit), int(offset)),
        )
    else:
        cur.execute(
            """
            SELECT alert_id, message, url, created_at, is_read
            FROM alerts
            WHERE user_id = ? AND (is_read IS NULL OR is_read = 0)
            ORDER BY alert_id DESC
            LIMIT ?
            OFFSET ?
            """,
            (int(user_id), int(limit), int(offset)),
        )
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "alert_id": row[0],
            "message": row[1],
            "url": row[2],
            "created_at": row[3],
            "is_read": bool(row[4]) if row[4] is not None else False,
        }
        for row in rows
    ]


def get_unread_alert_count(user_id: int) -> int:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT COUNT(*)
        FROM alerts
        WHERE user_id = ? AND (is_read IS NULL OR is_read = 0)
        """,
        (int(user_id),),
    )
    row = cur.fetchone()
    conn.close()
    return int(row[0] or 0) if row else 0


def mark_alert_read(alert_id: int, user_id: int):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE alerts
        SET is_read = 1
        WHERE alert_id = ? AND user_id = ?
        """,
        (alert_id, user_id),
    )
    conn.commit()
    conn.close()


def delete_alert_for_user(alert_id: int, user_id: int):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        DELETE FROM alerts
        WHERE alert_id = ? AND user_id = ?
        """,
        (int(alert_id), int(user_id)),
    )
    conn.commit()
    conn.close()


def get_alert_for_user(alert_id: int, user_id: int):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT alert_id, message, url, created_at, is_read
        FROM alerts
        WHERE alert_id = ? AND user_id = ?
        LIMIT 1
        """,
        (int(alert_id), int(user_id)),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "alert_id": row[0],
        "message": row[1],
        "url": row[2],
        "created_at": row[3],
        "is_read": bool(row[4]) if row[4] is not None else False,
    }


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


def is_following(followed_user_id, follower_user_id) -> bool:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT unfollowed
        FROM follow_info
        WHERE user_followed_key = ? AND followed_by_user_key = ?
        ORDER BY follow_info_key DESC
        LIMIT 1
        """,
        (followed_user_id, follower_user_id),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return False
    unfollowed = row[0]
    return not bool(unfollowed)


def follow_user(followed_user_id, follower_user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT follow_info_key
        FROM follow_info
        WHERE user_followed_key = ? AND followed_by_user_key = ?
        ORDER BY follow_info_key DESC
        LIMIT 1
        """,
        (followed_user_id, follower_user_id),
    )
    row = cur.fetchone()
    if row:
        cur.execute(
            "UPDATE follow_info SET unfollowed = 0 WHERE follow_info_key = ?",
            (row[0],),
        )
    else:
        cur.execute(
            """
            INSERT INTO follow_info (user_followed_key, followed_by_user_key, unfollowed)
            VALUES (?,?,0)
            """,
            (followed_user_id, follower_user_id),
        )
    conn.commit()
    conn.close()


def unfollow_user(followed_user_id, follower_user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE follow_info
        SET unfollowed = 1
        WHERE user_followed_key = ? AND followed_by_user_key = ?
        """,
        (followed_user_id, follower_user_id),
    )
    conn.commit()
    conn.close()


def get_followers(user_id: int, limit: int = 200, offset: int = 0):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT DISTINCT
            user_info.user_info_key,
            user_info.username,
            user_info.profile_pic
        FROM follow_info
        JOIN user_info ON user_info.user_info_key = follow_info.followed_by_user_key
        WHERE follow_info.user_followed_key = ?
          AND (follow_info.unfollowed IS NULL OR follow_info.unfollowed = 0)
        ORDER BY user_info.username COLLATE NOCASE ASC
                LIMIT ?
                OFFSET ?
        """,
        (int(user_id), int(limit), int(offset)),
    )
    rows = cur.fetchall()
    conn.close()
    return [
        {"user_id": row[0], "username": row[1], "profile_pic": row[2]} for row in rows
    ]


def count_followers(user_id: int) -> int:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT COUNT(1)
        FROM follow_info
        WHERE user_followed_key = ?
          AND (unfollowed IS NULL OR unfollowed = 0)
        """,
        (int(user_id),),
    )
    row = cur.fetchone()
    conn.close()
    try:
        return int(row[0]) if row and row[0] is not None else 0
    except (TypeError, ValueError):
        return 0


def get_unread_alert_sig(user_id: int) -> tuple[int, int]:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            COUNT(1) AS c,
            COALESCE(MAX(alert_id), 0) AS max_id
        FROM alerts
        WHERE user_id = ?
          AND (is_read IS NULL OR is_read = 0)
        """,
        (int(user_id),),
    )
    row = cur.fetchone()
    conn.close()
    try:
        c = int(row[0]) if row and row[0] is not None else 0
    except (TypeError, ValueError):
        c = 0
    try:
        max_id = int(row[1]) if row and row[1] is not None else 0
    except (TypeError, ValueError):
        max_id = 0
    return (max(0, c), max(0, max_id))


def get_following(user_id: int, limit: int = 200, offset: int = 0):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT DISTINCT
            user_info.user_info_key,
            user_info.username,
            user_info.profile_pic
        FROM follow_info
        JOIN user_info ON user_info.user_info_key = follow_info.user_followed_key
        WHERE follow_info.followed_by_user_key = ?
          AND (follow_info.unfollowed IS NULL OR follow_info.unfollowed = 0)
        ORDER BY user_info.username COLLATE NOCASE ASC
                LIMIT ?
                OFFSET ?
        """,
        (int(user_id), int(limit), int(offset)),
    )
    rows = cur.fetchall()
    conn.close()
    return [
        {"user_id": row[0], "username": row[1], "profile_pic": row[2]} for row in rows
    ]


def count_following(user_id: int) -> int:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT COUNT(1)
        FROM follow_info
        WHERE followed_by_user_key = ?
          AND (unfollowed IS NULL OR unfollowed = 0)
        """,
        (int(user_id),),
    )
    row = cur.fetchone()
    conn.close()
    try:
        return int(row[0]) if row and row[0] is not None else 0
    except (TypeError, ValueError):
        return 0
