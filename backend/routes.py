from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    flash,
    current_app,
    session,
    jsonify,
    Response,
)
from datetime import datetime, timezone, timedelta
from urllib.parse import urlsplit, urlunsplit
from urllib.parse import urlencode, quote
import os
import time
import re
import requests
import threading
from werkzeug.utils import secure_filename
from pathlib import Path
from flask_login import login_user, logout_user, login_required, current_user
import random
import uuid

from backend.database import (
    get_ratings,
    get_ratings_by_type,
    get_rating_by_key,
    add_rating,
    update_rating,
    delete_rating,
    create_user,
    get_user_by_id,
    get_user_by_username_or_email,
    get_user_by_username,
    search_users_by_username,
    search_ratings,
    search_playlists,
    get_ratings_by_user,
    get_ratings_by_user_paginated,
    verify_password,
    get_rating_owner,
    update_profile_pic,
    update_profile_info,
    get_profile_pic_by_username,
    get_profile_pics_by_usernames,
    get_profile_comments as get_profile_comments_db,
    add_profile_comment as add_profile_comment_db,
    update_profile_comment as update_profile_comment_db,
    delete_profile_comment as delete_profile_comment_db,
    create_alert,
    follow_user,
    unfollow_user,
    is_following,
    get_followers,
    get_following,
    count_followers,
    count_following,
    add_bulletin_post,
    add_activity,
    get_activity_feed_for_user,
    toggle_rating_like,
    is_rating_liked_by_user,
    get_liked_ratings_for_user,
    get_upvoted_ratings_for_user,
    get_upvoted_categories_for_user_ratings,
    add_playlist,
    get_playlists_by_creator,
    get_playlists_by_following,
    get_playlist_by_key,
    get_playlist_songs,
    add_song_to_playlist,
    add_song,
    search_songs,
    remove_song_from_playlist,
    delete_playlist,
    is_playlist_favorited_by_user,
    toggle_playlist_favorite,
    get_favorited_playlists_for_user,
    delete_bulletin_post,
    get_alerts_for_user,
    get_unread_alert_count,
    get_alert_for_user,
    delete_alert_for_user,
    mark_alert_read,
    get_bulletin_feed_for_user,
    get_bulletin_post_for_user,
    count_bulletin_feed_for_user,
    count_activity_feed_for_user,
    dismiss_activity_for_user,
    clear_activity_for_user,
    set_rating_category_vote,
    get_rating_category_votes_summary,
    get_user_rating_category_votes,
    get_category_vote_totals_for_ratings,
    get_rating_comments,
    add_rating_comment,
    get_rating_comment,
    update_rating_comment,
    delete_rating_comment,
    get_users,
    count_users,
    get_users_who_rated_same_subject,
    count_users_who_rated_same_subject,
    get_subject_activity_timeseries,
    search_rated_subjects,
    get_subject_overall_summary,
    get_ratings_for_subject,
    get_ratings_for_artist_including_works,
    get_top_rated_subjects,
    get_rating_reactions_summary,
    get_user_rating_reactions,
    toggle_rating_reaction,
    activity_exists,
    get_reaction_counts_for_ratings,
    get_subject_rating_emoji_counts_for_rating_keys,
    get_rating_emojis_for_rating_keys,
    get_top_subject_rating_emojis,
    strip_artist_features,
    get_cached_subject_image,
    set_cached_subject_image,
    get_rating_extras_by_key,
)

# Initialize routes with Blueprint
# Blueprint is what allows the routes to work (@app.route etc.)
app = Blueprint("main", __name__)


_PROXY_IMAGE_HOSTS = {
    "coverartarchive.org",
    "archive.org",
    "s3.us.archive.org",
    "commons.wikimedia.org",
    "upload.wikimedia.org",
}


def _is_proxyable_image_url(url: str | None) -> bool:
    raw = (url or "").strip()
    if not raw:
        return False
    try:
        parsed = urlsplit(raw)
    except Exception:
        return False
    if (parsed.scheme or "").lower() not in {"http", "https"}:
        return False
    host = (parsed.netloc or "").split(":", 1)[0].strip().lower()
    if not host:
        return False
    return host in _PROXY_IMAGE_HOSTS or host.endswith(".archive.org")


def _proxied_image_url(url: str | None) -> str | None:
    raw = (url or "").strip()
    if not raw:
        return None
    if not _is_proxyable_image_url(raw):
        return raw
    return "/image-proxy?" + urlencode({"url": raw})


@app.app_context_processor
def inject_image_proxy_helpers():
    return {"proxied_image_url": _proxied_image_url}


# Browse page (list all ratings)
@app.route("/browse")
def browse():
    raw_type = request.args.get("type", "all").strip().lower()
    active_type = (
        raw_type if raw_type in {"all", "songs", "albums", "artists"} else "all"
    )

    raw_order = (request.args.get("order") or "recent").strip().lower()
    active_order = raw_order if raw_order in {"recent", "oldest"} else "recent"

    page, per_page, offset = _parse_pagination()
    limit = per_page + 1

    if active_type == "songs":
        raw_ratings = get_ratings_by_type(
            "Song",
            limit=limit,
            offset=offset,
            order=active_order,
        )
    elif active_type == "albums":
        raw_ratings = get_ratings_by_type(
            "Album",
            limit=limit,
            offset=offset,
            order=active_order,
        )
    elif active_type == "artists":
        raw_ratings = get_ratings_by_type(
            "Artist",
            limit=limit,
            offset=offset,
            order=active_order,
        )
    else:
        raw_ratings = get_ratings(limit=limit, offset=offset, order=active_order)

    has_next = len(raw_ratings) > per_page
    ratings = raw_ratings[:per_page]

    owner_pics = _get_owner_pics_for_ratings(ratings)
    reactions_map = _build_subject_rating_emojis_map(ratings)
    percent_map = _build_percent_map(ratings)

    return render_template(
        "browse.html",
        ratings=ratings,
        active_type=active_type,
        active_order=active_order,
        owner_pics=owner_pics,
        reactions_map=reactions_map,
        percent_map=percent_map,
        pagination=_pagination_context(
            page=page,
            per_page=per_page,
            has_next=has_next,
            item_count=len(ratings),
        ),
    )


@app.route("/search", methods=["GET"])
def search():
    query = request.args.get("q", "").strip()

    tabs = [
        {"key": "all", "label": "All"},
        {"key": "users", "label": "Users"},
        {"key": "playlists", "label": "Playlists"},
        {"key": "ratings", "label": "Ratings"},
    ]
    allowed_tabs = {t["key"] for t in tabs}
    active_tab = (request.args.get("tab") or "all").strip().lower()
    if active_tab not in allowed_tabs:
        active_tab = "all"

    page, per_page, offset = _parse_pagination()
    limit = per_page + 1

    users_raw = []
    playlists_raw = []
    ratings_raw = []
    if query:
        if active_tab in {"all", "users"}:
            users_raw = search_users_by_username(query, limit=limit, offset=offset)
        if active_tab in {"all", "playlists"}:
            playlists_raw = search_playlists(query, limit=limit, offset=offset)
        if active_tab in {"all", "ratings"}:
            ratings_raw = search_ratings(query, limit=limit, offset=offset)

    if active_tab == "users":
        has_next = len(users_raw) > per_page
    elif active_tab == "playlists":
        has_next = len(playlists_raw) > per_page
    elif active_tab == "ratings":
        has_next = len(ratings_raw) > per_page
    else:
        has_next = (
            len(users_raw) > per_page
            or len(playlists_raw) > per_page
            or len(ratings_raw) > per_page
        )

    users = users_raw[:per_page]
    playlists = playlists_raw[:per_page]
    ratings = ratings_raw[:per_page]

    owner_pics = _get_owner_pics_for_ratings(ratings)
    reactions_map = _build_reactions_map(ratings)
    percent_map = _build_percent_map(ratings)
    return render_template(
        "search.html",
        tabs=tabs,
        active_tab=active_tab,
        query=query,
        users=users,
        playlists=playlists,
        ratings=ratings,
        owner_pics=owner_pics,
        reactions_map=reactions_map,
        percent_map=percent_map,
        pagination=_pagination_context(
            page=page,
            per_page=per_page,
            has_next=has_next,
            item_count=(
                len(users)
                if active_tab == "users"
                else (
                    len(playlists)
                    if active_tab == "playlists"
                    else (
                        len(ratings)
                        if active_tab == "ratings"
                        else (len(users) + len(playlists) + len(ratings))
                    )
                )
            ),
        ),
    )


@app.route("/favorites")
def favorites():
    raw_tab = request.args.get("tab", "ratings").strip().lower()
    active_tab = (
        raw_tab if raw_tab in {"ratings", "playlists", "upvoted"} else "ratings"
    )

    page, per_page, offset = _parse_pagination()
    limit = per_page + 1

    if not current_user.is_authenticated:
        return render_template(
            "favorites.html",
            ratings=[],
            playlists=[],
            active_tab=active_tab,
            owner_pics={},
            reactions_map={},
            percent_map={},
            upvoted_categories_map={},
            pagination=None,
        )

    if active_tab == "playlists":
        raw_playlists = get_favorited_playlists_for_user(
            current_user.id,
            limit=limit,
            offset=offset,
        )
        has_next = len(raw_playlists) > per_page
        playlists = raw_playlists[:per_page]
        ratings = []
        upvoted_categories_map = {}
    elif active_tab == "upvoted":
        raw_ratings = get_upvoted_ratings_for_user(
            current_user.id,
            limit=limit,
            offset=offset,
        )
        has_next = len(raw_ratings) > per_page
        ratings = raw_ratings[:per_page]
        playlists = []
        upvoted_categories_map = get_upvoted_categories_for_user_ratings(
            current_user.id,
            [r[0] for r in ratings],
        )
    else:
        raw_ratings = get_liked_ratings_for_user(
            current_user.id,
            limit=limit,
            offset=offset,
        )
        has_next = len(raw_ratings) > per_page
        ratings = raw_ratings[:per_page]
        playlists = []
        upvoted_categories_map = {}

    owner_pics = _get_owner_pics_for_ratings(ratings)
    reactions_map = _build_reactions_map(ratings)
    percent_map = _build_percent_map(ratings)

    return render_template(
        "favorites.html",
        ratings=ratings,
        playlists=playlists,
        active_tab=active_tab,
        owner_pics=owner_pics,
        reactions_map=reactions_map,
        percent_map=percent_map,
        upvoted_categories_map=upvoted_categories_map,
        pagination=_pagination_context(
            page=page,
            per_page=per_page,
            has_next=has_next,
            item_count=(len(playlists) if active_tab == "playlists" else len(ratings)),
        ),
    )


@app.route("/alerts/<int:alert_id>/go")
@login_required
def alert_go(alert_id: int):
    alert = get_alert_for_user(alert_id, current_user.id)
    next_url = request.args.get("next", "").strip()

    if not alert:
        flash("Alert not found.", "error")
        return redirect(next_url or "/")

    dest = (alert.get("url") or "").strip() or next_url or "/"

    mark_alert_read(alert_id, current_user.id)

    try:
        parts = urlsplit(dest)
        if parts.scheme or parts.netloc:
            dest = "/"
        elif not parts.path.startswith("/"):
            dest = "/"
        else:
            dest = urlunsplit(("", "", parts.path, parts.query, ""))
    except Exception:
        dest = "/"

    return redirect(dest)


@app.route("/alerts")
@login_required
def alerts_page():
    page, per_page, offset = _parse_pagination()
    raw_alerts = get_alerts_for_user(
        current_user.id,
        limit=per_page + 1,
        include_read=True,
        offset=offset,
    )
    has_next = len(raw_alerts) > per_page
    alerts = raw_alerts[:per_page]

    for a in alerts:
        a["time_ago"] = _format_time_ago(a.get("created_at") or "")

    unread_alert_count = get_unread_alert_count(current_user.id)
    return render_template(
        "alerts.html",
        items=alerts,
        unread_alert_count=unread_alert_count,
        pagination=_pagination_context(
            page=page,
            per_page=per_page,
            has_next=has_next,
            item_count=len(alerts),
        ),
    )


@app.route("/alerts/<int:alert_id>/delete", methods=["POST"])
@login_required
def delete_alert(alert_id: int):
    alert = get_alert_for_user(alert_id, current_user.id)
    next_url = (
        request.args.get("next", "").strip() or request.form.get("next", "").strip()
    )

    if not alert:
        flash("Alert not found.", "error")
        return redirect(next_url or "/alerts")

    delete_alert_for_user(alert_id, current_user.id)
    flash("Alert deleted.", "success")

    dest = next_url or "/alerts"
    try:
        parts = urlsplit(dest)
        if parts.scheme or parts.netloc:
            dest = "/alerts"
        elif not parts.path.startswith("/"):
            dest = "/alerts"
        else:
            dest = urlunsplit(("", "", parts.path, parts.query, ""))
    except Exception:
        dest = "/alerts"

    return redirect(dest)


@app.route("/playlists")
def playlists():
    if not current_user.is_authenticated:
        return render_template(
            "playlists.html",
            playlists=[],
            active_tab="my",
            pagination=None,
        )

    raw_tab = request.args.get("tab", "my").strip().lower()
    active_tab = raw_tab if raw_tab in {"my", "following"} else "my"

    page, per_page, offset = _parse_pagination()
    limit = per_page + 1

    if active_tab == "following":
        raw_playlists = get_playlists_by_following(
            current_user.id,
            limit=limit,
            offset=offset,
        )
    else:
        raw_playlists = get_playlists_by_creator(
            current_user.username,
            limit=limit,
            offset=offset,
        )

    has_next = len(raw_playlists) > per_page
    playlists = raw_playlists[:per_page]

    return render_template(
        "playlists.html",
        playlists=playlists,
        active_tab=active_tab,
        pagination=_pagination_context(
            page=page,
            per_page=per_page,
            has_next=has_next,
            item_count=len(playlists),
        ),
    )


@app.route("/playlists/<int:playlist_key>")
def playlist_detail(playlist_key: int):
    playlist = get_playlist_by_key(playlist_key)
    if not playlist:
        flash("Playlist not found.", "error")
        return redirect("/playlists")

    songs = get_playlist_songs(playlist_key, limit=500)
    can_edit = (
        current_user.is_authenticated
        and (playlist[1] or "").strip().lower() == current_user.username.strip().lower()
    )

    is_favorited = current_user.is_authenticated and is_playlist_favorited_by_user(
        playlist_key, current_user.id
    )

    q = request.args.get("q", "").strip()
    search_results = search_songs(q, limit=30) if (can_edit and q) else []
    return render_template(
        "playlist-detail.html",
        playlist=playlist,
        songs=songs,
        can_edit=can_edit,
        is_favorited=is_favorited,
        q=q,
        search_results=search_results,
    )


@app.route("/playlists/<int:playlist_key>/favorite", methods=["POST"])
@login_required
def playlist_toggle_favorite(playlist_key: int):
    playlist = get_playlist_by_key(playlist_key)
    if not playlist:
        flash("Playlist not found.", "error")
        return redirect("/playlists")

    new_favorited = toggle_playlist_favorite(playlist_key, current_user.id)

    playlist_title = (playlist[2] or "").strip()
    add_activity(
        current_user.id,
        current_user.username,
        action="playlist_favorite" if new_favorited else "playlist_unfavorite",
        category="playlists",
        entity_type="playlist",
        entity_id=playlist_key,
        entity_label=playlist_title or f"Playlist {playlist_key}",
        url=f"/playlists/{playlist_key}",
    )

    flash(
        (
            "Playlist added to favorites."
            if new_favorited
            else "Playlist removed from favorites."
        ),
        "success" if new_favorited else "info",
    )
    return redirect(f"/playlists/{playlist_key}")


@app.route("/playlists/<int:playlist_key>/songs", methods=["POST"])
@login_required
def playlist_add_songs(playlist_key: int):
    playlist = get_playlist_by_key(playlist_key)
    if not playlist:
        flash("Playlist not found.", "error")
        return redirect("/playlists")

    if (playlist[1] or "").strip().lower() != current_user.username.strip().lower():
        flash("You can only edit your own playlists.", "error")
        return redirect(f"/playlists/{playlist_key}")

    song_key = request.form.get("song_key", "").strip()
    if not song_key.isdigit():
        flash("Select a song to add.", "error")
        return redirect(f"/playlists/{playlist_key}")

    ok = add_song_to_playlist(playlist_key, current_user.username, int(song_key))
    if ok:
        flash("Song added to playlist.", "success")
    else:
        flash("Could not add song (missing or already added).", "error")
    return redirect(f"/playlists/{playlist_key}")


@app.route("/playlists/<int:playlist_key>/songs/new", methods=["POST"])
@login_required
def playlist_create_and_add_song(playlist_key: int):
    playlist = get_playlist_by_key(playlist_key)
    if not playlist:
        flash("Playlist not found.", "error")
        return redirect("/playlists")

    if (playlist[1] or "").strip().lower() != current_user.username.strip().lower():
        flash("You can only edit your own playlists.", "error")
        return redirect(f"/playlists/{playlist_key}")

    title = request.form.get("title", "")
    artist_name = request.form.get("artist_name", "")
    song_link = request.form.get("song_link", "").strip()
    if song_link and not (
        song_link.startswith("http://") or song_link.startswith("https://")
    ):
        flash("Song link must start with http:// or https://", "error")
        return redirect(f"/playlists/{playlist_key}")

    song_key = add_song(
        title,
        artist_name,
        song_link=song_link,
        uploaded_by=current_user.username,
    )
    if song_key is None:
        flash("Song title is required.", "error")
        return redirect(f"/playlists/{playlist_key}")

    add_song_to_playlist(playlist_key, current_user.username, song_key)
    flash("Song added to playlist.", "success")
    return redirect(f"/playlists/{playlist_key}")


@app.route(
    "/playlists/<int:playlist_key>/songs/<int:song_key>/delete", methods=["POST"]
)
@login_required
def playlist_delete_song(playlist_key: int, song_key: int):
    playlist = get_playlist_by_key(playlist_key)
    if not playlist:
        flash("Playlist not found.", "error")
        return redirect("/playlists")

    if (playlist[1] or "").strip().lower() != current_user.username.strip().lower():
        flash("You can only edit your own playlists.", "error")
        return redirect(f"/playlists/{playlist_key}")

    ok = remove_song_from_playlist(playlist_key, song_key)
    if ok:
        flash("Song removed from playlist.", "success")
    else:
        flash("Could not remove song.", "error")

    return redirect(f"/playlists/{playlist_key}")


@app.route("/playlists/<int:playlist_key>/delete", methods=["POST"])
@login_required
def playlist_delete(playlist_key: int):
    playlist = get_playlist_by_key(playlist_key)
    if not playlist:
        flash("Playlist not found.", "error")
        return redirect("/playlists")

    if (playlist[1] or "").strip().lower() != current_user.username.strip().lower():
        flash("You can only delete your own playlists.", "error")
        return redirect(f"/playlists/{playlist_key}")

    ok = delete_playlist(playlist_key)
    if ok:
        flash("Playlist deleted.", "success")
    else:
        flash("Could not delete playlist.", "error")
    return redirect("/playlists")


@app.route("/playlists/create", methods=["POST"])
@login_required
def playlists_create():
    title = request.form.get("title", "")
    description = request.form.get("description", "")

    playlist_key = add_playlist(current_user.username, title, description)
    if playlist_key is None:
        flash("Playlist title is required.", "error")
    else:
        flash("Playlist created.", "success")
    return redirect("/playlists")


@app.route("/analytics")
def analytics():
    return render_template("analytics.html")


@app.route("/charts")
def charts():
    raw_kind = (request.args.get("kind") or "song").strip().lower()
    kind = raw_kind if raw_kind in {"song", "album", "artist"} else "song"

    page, per_page, offset = _parse_pagination(
        default_per_page=25,
        allowed_per_page=(5, 10, 25, 50, 100),
    )

    raw_items = get_top_rated_subjects(
        kind=kind,
        limit=per_page + 1,
        offset=offset,
        min_ratings=1,
    )
    has_next = len(raw_items) > per_page
    items = raw_items[:per_page]

    def _details_url(it: dict) -> str:
        params: dict[str, str] = {"kind": kind}
        mbid = (it.get("mbid") or "").strip()
        name = (it.get("name") or "").strip()
        artist = (it.get("artist") or "").strip()
        if mbid:
            params["mbid"] = mbid
        if name:
            params["name"] = name
        if kind != "artist" and artist:
            params["artist"] = artist
        return "/also-rated?" + urlencode(params)

    for it in items or []:
        try:
            it["details_url"] = _details_url(it)
        except Exception:
            it["details_url"] = "/charts"

    return render_template(
        "charts.html",
        kind=kind,
        items=items or [],
        rank_offset=offset,
        pagination=_pagination_context(
            page=page,
            per_page=per_page,
            has_next=has_next,
            item_count=len(items),
            options=[5, 10, 25, 50, 100],
        ),
    )


@app.route("/api/charts/subjects", methods=["GET"])
def charts_subjects_api():
    raw_kind = (request.args.get("kind") or "song").strip().lower()
    kind = raw_kind if raw_kind in {"song", "album", "artist"} else "song"
    q = (request.args.get("q") or "").strip()
    artist = (request.args.get("artist") or "").strip()
    try:
        limit = int((request.args.get("limit") or "10").strip())
    except ValueError:
        limit = 10
    limit = max(1, min(50, limit))

    items = search_rated_subjects(kind=kind, q=q, artist=artist, limit=limit)
    return jsonify({"ok": True, "kind": kind, "items": items})


@app.route("/api/charts/top", methods=["GET"])
def charts_top_api():
    raw_kind = (request.args.get("kind") or "song").strip().lower()
    kind = raw_kind if raw_kind in {"song", "album", "artist"} else "song"

    try:
        limit = int((request.args.get("limit") or "25").strip())
    except ValueError:
        limit = 25
    limit = max(1, min(100, limit))

    try:
        min_ratings = int((request.args.get("min_ratings") or "1").strip())
    except ValueError:
        min_ratings = 1
    min_ratings = max(1, min(50, min_ratings))

    items = get_top_rated_subjects(kind=kind, limit=limit, min_ratings=min_ratings)
    return jsonify({"ok": True, "kind": kind, "items": items})


@app.route("/api/charts/subject-activity", methods=["GET"])
def charts_subject_activity_api():
    raw_kind = (request.args.get("kind") or "song").strip().lower()
    kind = raw_kind if raw_kind in {"song", "album", "artist"} else "song"
    rating_type = {"song": "Song", "album": "Album", "artist": "Artist"}[kind]

    mbid = (request.args.get("mbid") or "").strip() or None
    name = (request.args.get("name") or "").strip()
    artist = (request.args.get("artist") or "").strip()

    raw_action = (request.args.get("action") or "rating_create").strip().lower()
    allowed_actions = {
        "rating_create",
        "rating_view",
        "rating_like",
        "rating_unlike",
        "rating_edit",
        "rating_delete",
    }
    action = raw_action if raw_action in allowed_actions else "rating_create"

    raw_days = (request.args.get("days") or "90").strip()
    try:
        days = int(raw_days)
    except ValueError:
        days = 90
    days = max(1, min(3650, days))
    cutoff_iso = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    if not mbid and not name:
        return jsonify({"ok": False, "error": "Missing subject"}), 400

    series = get_subject_activity_timeseries(
        action=action,
        mbid=mbid,
        rating_type=rating_type,
        rating_name=name,
        content_artist=artist if kind != "artist" else "",
        cutoff_iso=cutoff_iso,
        days=days,
    )

    def _format_chart_label(bucket: str, d: int) -> str:
        if d <= 1 and "T" in (bucket or ""):
            try:
                parts = (bucket or "").split("T")
                h = int((parts[-1] or "0")[:2])
                if h == 0:
                    return "12a"
                if h == 12:
                    return "12p"
                return f"{h % 12}{'a' if h < 12 else 'p'}"
            except (ValueError, TypeError):
                return bucket or ""
        if len(bucket or "") >= 10:
            try:
                dt = datetime.fromisoformat((bucket or "")[:10].replace("Z", "+00:00"))
                return dt.strftime("%b %d")
            except (ValueError, TypeError):
                return bucket or ""
        if len(bucket or "") >= 7:
            try:
                y, m = (bucket or "")[:4], (bucket or "")[5:7]
                mon = datetime(2000, int(m), 1).strftime("%b")
                return f"{mon} {y}"
            except (ValueError, TypeError):
                return bucket or ""
        return bucket or ""

    labels = [_format_chart_label(p["day"], days) for p in series]

    return jsonify(
        {
            "ok": True,
            "kind": kind,
            "action": action,
            "days": days,
            "labels": labels,
            "events": [p["event_count"] for p in series],
            "users": [p["user_count"] for p in series],
        }
    )


@app.route("/api/charts/subject-summary", methods=["GET"])
def charts_subject_summary_api():
    raw_kind = (request.args.get("kind") or "song").strip().lower()
    kind = raw_kind if raw_kind in {"song", "album", "artist"} else "song"
    rating_type = {"song": "Song", "album": "Album", "artist": "Artist"}[kind]

    mbid = (request.args.get("mbid") or "").strip() or None
    name = (request.args.get("name") or "").strip()
    artist = (request.args.get("artist") or "").strip()

    if not mbid and not name:
        return jsonify({"ok": False, "error": "Missing subject"}), 400

    summary = get_subject_overall_summary(
        mbid=mbid,
        rating_type=rating_type,
        rating_name=name,
        content_artist=artist if kind != "artist" else "",
    )
    if not summary:
        return jsonify({"ok": True, "summary": None})

    return jsonify({"ok": True, "summary": summary})


@app.route("/users")
def users():
    page, per_page, offset = _parse_pagination(default_per_page=20)
    active_order = (request.args.get("order") or "newest").strip().lower()
    if active_order not in {"az", "za", "newest", "oldest", "cred_high", "cred_low"}:
        active_order = "newest"

    raw_items = get_users(limit=per_page + 1, offset=offset, order=active_order)
    has_next = len(raw_items) > per_page
    items = raw_items[:per_page]
    total_count = count_users()

    return render_template(
        "users.html",
        items=items,
        total_count=total_count,
        active_order=active_order,
        pagination=_pagination_context(
            page=page,
            per_page=per_page,
            has_next=has_next,
            item_count=len(items),
        ),
    )


@app.route("/genres")
def genres():
    return render_template("genres.html")


@app.route("/activity")
@login_required
def activity():
    tabs = [
        {"key": "all", "label": "All"},
        {"key": "users", "label": "Users"},
        {"key": "artists", "label": "Artists"},
        {"key": "albums", "label": "Albums"},
        {"key": "songs", "label": "Songs"},
        {"key": "genres", "label": "Genres"},
    ]

    allowed_tabs = {t["key"] for t in tabs}
    active_tab = (request.args.get("tab") or "all").strip().lower()
    if active_tab not in allowed_tabs:
        active_tab = "all"

    page, per_page, offset = _parse_pagination()
    limit = per_page + 1

    raw_items = get_activity_feed_for_user(
        current_user.id,
        limit=limit,
        category=None if active_tab == "all" else active_tab,
        offset=offset,
    )

    has_next = len(raw_items) > per_page
    raw_items = raw_items[:per_page]

    def _format_activity(item: dict) -> dict:
        actor = item.get("actor_username") or ""
        action = item.get("action") or ""
        entity_label = item.get("entity_label") or ""
        url = item.get("url") or ""
        metadata = item.get("metadata") or {}
        created_at = item.get("created_at")
        time_ago = _format_time_ago(created_at)

        if action == "follow":
            text = f"@{actor} followed {entity_label or 'a user'}"
        elif action == "unfollow":
            text = f"@{actor} unfollowed {entity_label or 'a user'}"
        elif action == "rating_create":
            text = (
                f"@{actor} created a rating: {entity_label}"
                if entity_label
                else f"@{actor} created a rating"
            )
        elif action == "rating_edit":
            text = (
                f"@{actor} edited a rating: {entity_label}"
                if entity_label
                else f"@{actor} edited a rating"
            )
        elif action == "rating_delete":
            text = (
                f"@{actor} deleted a rating: {entity_label}"
                if entity_label
                else f"@{actor} deleted a rating"
            )
        elif action == "rating_view":
            text = (
                f"@{actor} viewed a rating: {entity_label}"
                if entity_label
                else f"@{actor} viewed a rating"
            )
        elif action == "rating_like":
            text = (
                f"@{actor} liked a rating: {entity_label}"
                if entity_label
                else f"@{actor} liked a rating"
            )
        elif action == "rating_unlike":
            text = (
                f"@{actor} unliked a rating: {entity_label}"
                if entity_label
                else f"@{actor} unliked a rating"
            )
        elif action == "rating_reaction":
            text = (
                f"@{actor} reacted to a rating: {entity_label}"
                if entity_label
                else f"@{actor} reacted to a rating"
            )
        elif action == "rating_category_upvote":
            detail = (metadata.get("detail") or "").strip() or "a category"
            text = (
                f"@{actor} upvoted {detail} on a rating: {entity_label}"
                if entity_label
                else f"@{actor} upvoted {detail} on a rating"
            )
        elif action == "rating_category_downvote":
            detail = (metadata.get("detail") or "").strip() or "a category"
            text = (
                f"@{actor} downvoted {detail} on a rating: {entity_label}"
                if entity_label
                else f"@{actor} downvoted {detail} on a rating"
            )
        elif action == "rating_category_unvote":
            detail = (metadata.get("detail") or "").strip() or "a category"
            text = (
                f"@{actor} removed their vote on {detail} for a rating: {entity_label}"
                if entity_label
                else f"@{actor} removed their vote on {detail} for a rating"
            )
        elif action == "rating_comment_add":
            text = (
                f"@{actor} commented on a rating: {entity_label}"
                if entity_label
                else f"@{actor} commented on a rating"
            )
        elif action == "rating_comment_edit":
            text = (
                f"@{actor} edited a rating comment: {entity_label}"
                if entity_label
                else f"@{actor} edited a rating comment"
            )
        elif action == "rating_comment_delete":
            text = (
                f"@{actor} deleted a rating comment: {entity_label}"
                if entity_label
                else f"@{actor} deleted a rating comment"
            )
        elif action == "playlist_favorite":
            text = (
                f"@{actor} favorited a playlist: {entity_label}"
                if entity_label
                else f"@{actor} favorited a playlist"
            )
        elif action == "playlist_unfavorite":
            text = (
                f"@{actor} unfavorited a playlist: {entity_label}"
                if entity_label
                else f"@{actor} unfavorited a playlist"
            )
        elif action == "bulletin_post":
            text = f"@{actor} posted to the bulletin"
        elif action == "profile_comment_add":
            text = f"@{actor} commented on {entity_label or 'a profile'}"
        elif action == "profile_comment_edit":
            text = f"@{actor} edited a comment on {entity_label or 'a profile'}"
        elif action == "profile_comment_delete":
            text = f"@{actor} deleted a comment on {entity_label or 'a profile'}"
        elif action == "profile_update":
            text = f"@{actor} updated their profile"
        else:
            text = f"@{actor}: {action} {entity_label}".strip()

        return {
            **item,
            "text": text,
            "time_ago": time_ago,
            "url": url,
        }

    items = [_format_activity(i) for i in raw_items]

    total_count = count_activity_feed_for_user(
        current_user.id,
        category=None if active_tab == "all" else active_tab,
    )

    return render_template(
        "activity.html",
        tabs=tabs,
        active_tab=active_tab,
        items=items,
        total_count=total_count,
        pagination=_pagination_context(
            page=page,
            per_page=per_page,
            has_next=has_next,
            item_count=len(items),
        ),
    )


@app.route("/activity/<int:activity_id>/dismiss", methods=["POST"])
@login_required
def activity_dismiss(activity_id: int):
    next_url = (request.form.get("next") or "").strip()
    dismiss_activity_for_user(current_user.id, int(activity_id))
    if (request.headers.get("X-Requested-With") or "").lower() == "fetch":
        return jsonify({"ok": True, "activity_id": int(activity_id)})
    return redirect(_safe_internal_url(next_url, fallback="/activity"))


@app.route("/activity/clear", methods=["POST"])
@login_required
def activity_clear():
    next_url = (request.form.get("next") or "").strip()
    raw_tab = (request.form.get("tab") or "all").strip().lower()
    allowed_tabs = {"all", "users", "artists", "albums", "songs", "genres"}
    tab = raw_tab if raw_tab in allowed_tabs else "all"
    clear_activity_for_user(current_user.id, tab)
    if (request.headers.get("X-Requested-With") or "").lower() == "fetch":
        return jsonify({"ok": True, "tab": tab})
    flash("Activity cleared.", "success")
    return redirect(_safe_internal_url(next_url, fallback=f"/activity?tab={tab}"))


# Authentication page
@app.route("/auth")
def auth():
    session["auth_mode"] = "login"
    ref = request.referrer
    if ref and ref.startswith(request.host_url):
        return redirect(ref)
    return redirect("/")


@app.route("/auth/signup")
def auth_signup_mode():
    session["auth_mode"] = "signup"
    ref = request.referrer
    if ref and ref.startswith(request.host_url):
        return redirect(ref)
    return redirect("/")


@app.route("/auth/login")
def auth_login_mode():
    session["auth_mode"] = "login"
    ref = request.referrer
    if ref and ref.startswith(request.host_url):
        return redirect(ref)
    return redirect("/")


# Signup user
@app.route("/signup", methods=["POST"])
def signup():
    username = request.form.get("username", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")
    confirm = request.form.get("confirm_password", "")
    if not username or not email or not password or password != confirm:
        flash("Please complete all fields and ensure passwords match.", "error")
        session["auth_mode"] = "signup"
        ref = request.referrer
        if ref and ref.startswith(request.host_url):
            return redirect(ref)
        return redirect("/")
    user = create_user(username, email, password)
    if not user:  # if username or email taken
        flash("That username or email is already taken.", "error")
        session["auth_mode"] = "signup"
        ref = request.referrer
        if ref and ref.startswith(request.host_url):
            return redirect(ref)
        return redirect("/")
    login_user(user)
    next_url = session.pop("next_url", None)
    session.pop("auth_mode", None)
    if next_url and next_url.startswith("/"):
        return redirect(next_url)
    return redirect("/browse")


# Login user
@app.route("/login", methods=["POST"])
def login():
    identifier = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    user = get_user_by_username_or_email(identifier)
    if not user or not verify_password(user.password_hash, password):
        flash("Invalid username/email or password.", "error")
        session["auth_mode"] = "login"
        ref = request.referrer
        if ref and ref.startswith(request.host_url):
            return redirect(ref)
        return redirect("/")
    login_user(user)
    next_url = session.pop("next_url", None)
    session.pop("auth_mode", None)
    if next_url and next_url.startswith("/"):
        return redirect(next_url)
    return redirect("/browse")


# Logout user
@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect("/")


@app.route("/bulletin", methods=["GET", "POST"])
@login_required
def bulletin():
    if request.method == "GET":
        page, per_page, offset = _parse_pagination()
        raw_items = get_bulletin_feed_for_user(
            current_user.id,
            limit=per_page + 1,
            offset=offset,
        )
        has_next = len(raw_items) > per_page
        items = raw_items[:per_page]

        for p in items:
            p["time_ago"] = _format_time_ago(p.get("created_at") or "")

        total_count = count_bulletin_feed_for_user(current_user.id)
        return render_template(
            "bulletin.html",
            items=items,
            total_count=total_count,
            pagination=_pagination_context(
                page=page,
                per_page=per_page,
                has_next=has_next,
                item_count=len(items),
            ),
        )

    title = (request.form.get("title") or "").strip()
    message = (request.form.get("message") or "").strip()
    post_type = (request.form.get("type") or "").strip().lower()

    allowed_types = {
        "poll",
        "praise",
        "critique",
        "show & tell",
        "rating highlight",
        "rating challenge",
    }
    if post_type not in allowed_types:
        post_type = "praise"

    if not message:
        flash("Bulletin message cannot be empty.", "error")
        return redirect(request.referrer or "/")

    if len(title) > 80:
        flash("Bulletin title is too long (max 80 characters).", "error")
        return redirect(request.referrer or "/")

    if len(message) > 500:
        flash("Bulletin message is too long (max 500 characters).", "error")
        return redirect(request.referrer or "/")

    bulletin_key = add_bulletin_post(
        current_user.id,
        current_user.username,
        title,
        message,
        post_type=post_type,
    )

    try:
        followers = get_followers(int(current_user.id), limit=2000, offset=0) or []
    except Exception:
        followers = []
    for f in followers:
        try:
            follower_id = int((f or {}).get("user_id"))
        except (TypeError, ValueError):
            continue
        if follower_id == int(current_user.id):
            continue
        create_alert(
            follower_id,
            f"@{current_user.username} posted to the bulletin",
            url=f"/bulletin/{int(bulletin_key)}" if bulletin_key else "/bulletin",
        )
    add_activity(
        current_user.id,
        current_user.username,
        action="bulletin_post",
        category="users",
        entity_type="bulletin",
        entity_id=bulletin_key,
        entity_label=None,
        url=_safe_internal_url(request.referrer, "/"),
        metadata={
            "message_length": len(message),
            "title_length": len(title),
            "type": post_type,
        },
    )

    next_url = (request.form.get("next") or "").strip()
    if next_url and next_url.startswith("/"):
        return redirect(next_url)
    return redirect(request.referrer or "/")


@app.route("/bulletin/<int:bulletin_key>", methods=["GET"])
@login_required
def bulletin_post_page(bulletin_key: int):
    post = get_bulletin_post_for_user(current_user.id, bulletin_key)
    if not post:
        flash("Bulletin post not found.", "error")
        return redirect("/bulletin")

    post["time_ago"] = _format_time_ago(post.get("created_at") or "")
    return render_template(
        "bulletin_post.html",
        post=post,
    )


@app.route("/bulletin/<int:bulletin_key>/delete", methods=["POST"])
@login_required
def bulletin_delete(bulletin_key: int):
    ok = delete_bulletin_post(bulletin_key, current_user.id)
    if ok:
        flash("Bulletin post deleted.", "success")
    else:
        flash("You can only delete your own bulletin posts.", "error")

    next_url = (request.form.get("next") or "").strip()
    if next_url and next_url.startswith("/"):
        return redirect(next_url)
    return redirect(request.referrer or "/")


# View rating details
@app.route("/rating/<int:rating_key>")
def rating_detail(rating_key):
    rating = get_rating_by_key(rating_key)
    if not rating:
        return redirect(f"/rating/{rating_key}")

    rating_image_url = rating[-1] if len(rating) > 13 else None
    subject_artist = (rating[-2] if len(rating) > 14 else None) or None
    subject_mbid = (rating[-4] if len(rating) > 16 else None) or None
    rating_emoji = (rating[-5] if len(rating) > 17 else None) or None

    extra_link, extra_info = get_rating_extras_by_key(rating_key)

    subject_all_ratings_url = f"/rating/{int(rating_key)}/also-rated"
    artist_all_ratings_url = None
    rating_type_lc = (rating[1] or "").strip().lower()
    if rating_type_lc in {"song", "album"} and subject_artist:
        primary_artist = strip_artist_features(subject_artist)
        artist_all_ratings_url = "/also-rated?" + urlencode(
            {"kind": "artist", "name": str(primary_artist or subject_artist)}
        )

    owner = get_rating_owner(rating_key)

    liked = False
    if current_user.is_authenticated:
        liked = is_rating_liked_by_user(rating_key, current_user.id)

    category_vote_summary = get_rating_category_votes_summary(rating_key)
    user_category_votes = {}
    if current_user.is_authenticated:
        user_category_votes = get_user_rating_category_votes(
            rating_key, current_user.id
        )

    if current_user.is_authenticated:
        rating_type = (rating[1] or "").strip()
        rating_name = (rating[2] or "").strip()
        category = _category_from_rating_type(rating_type)
        add_activity(
            current_user.id,
            current_user.username,
            action="rating_view",
            category=category,
            entity_type="rating",
            entity_id=rating_key,
            entity_label=f"{rating_type}: {rating_name}".strip(": "),
            url=f"/rating/{rating_key}",
            metadata={"owner": owner},
        )

    percent = _build_percent_map([rating]).get(int(rating_key))

    reaction_summary = get_rating_reactions_summary(rating_key)
    user_reactions = {}
    if current_user.is_authenticated:
        user_reactions = get_user_rating_reactions(rating_key, current_user.id)

    owner_pic = get_profile_pic_by_username(owner) if owner else None
    if owner_pic and not _pic_exists(owner_pic):
        owner_pic = None
    comments = _build_rating_comments(rating_key)

    return render_template(
        "rating.html",
        rating=rating,
        rating_emoji=rating_emoji,
        extra_link=extra_link,
        extra_info=extra_info,
        owner=owner,
        owner_pic=owner_pic,
        percent=percent,
        liked=liked,
        rating_image_url=rating_image_url,
        subject_artist=subject_artist,
        subject_mbid=subject_mbid,
        subject_all_ratings_url=subject_all_ratings_url,
        artist_all_ratings_url=artist_all_ratings_url,
        category_vote_summary=category_vote_summary,
        user_category_votes=user_category_votes,
        can_category_vote=current_user.is_authenticated,
        comments=comments,
        reaction_summary=reaction_summary,
        user_reactions=user_reactions,
        reaction_emojis=REACTION_EMOJIS,
        can_react=current_user.is_authenticated,
    )


@app.route("/rating/<int:rating_key>/also-rated")
def rating_also_rated(rating_key: int):
    rating = get_rating_by_key(rating_key)
    if not rating:
        flash("Rating not found.", "error")
        return redirect("/")

    rating_type = (rating[1] or "").strip()
    rating_name = (rating[2] or "").strip()
    mbid = (rating[-4] if len(rating) > 16 else None) or None
    content_artist = (rating[-2] if len(rating) > 14 else None) or None
    artist_all_ratings_url = None
    if (rating_type or "").strip().lower() in {"song", "album"} and content_artist:
        primary_artist = strip_artist_features(content_artist)
        artist_all_ratings_url = "/also-rated?" + urlencode(
            {"kind": "artist", "name": str(primary_artist or content_artist)}
        )

    summary = get_subject_overall_summary(
        mbid=mbid,
        rating_type=rating_type,
        rating_name=rating_name,
        content_artist=content_artist,
    )

    allowed_tabs = {"all", "artist", "albums", "songs"}
    raw_tab = (request.args.get("tab") or "all").strip().lower()
    active_tab = raw_tab if raw_tab in allowed_tabs else "all"
    if (rating_type or "").strip().lower() != "artist":
        active_tab = "all"

    page, per_page, offset = _parse_pagination(default_per_page=20)
    limit = per_page + 1

    if (rating_type or "").strip().lower() == "artist":
        raw_ratings = get_ratings_for_artist_including_works(
            artist_name=rating_name,
            scope=active_tab,
            limit=limit,
            offset=offset,
            order="recent",
        )
    else:
        raw_ratings = get_ratings_for_subject(
            exclude_rating_key=0,
            mbid=mbid,
            rating_type=rating_type,
            rating_name=rating_name,
            content_artist=content_artist,
            limit=limit,
            offset=offset,
            order="recent",
        )

    if (rating_type or "").strip().lower() == "artist" and summary:
        fetched = _cached_artist_image_url(artist_name=rating_name, artist_mbid=mbid)
        if fetched:
            summary["image_url"] = fetched

    has_next = len(raw_ratings) > per_page
    ratings = raw_ratings[:per_page]

    tab_urls = None
    if (rating_type or "").strip().lower() == "artist":
        base = f"/rating/{int(rating_key)}/also-rated"
        common_params: dict[str, str] = {}
        if per_page:
            common_params["per_page"] = str(int(per_page))

        tab_urls = {}
        for t in ("all", "artist", "albums", "songs"):
            params = dict(common_params)
            if t != "all":
                params["tab"] = t
            tab_urls[t] = base + ("?" + urlencode(params) if params else "")
    owner_pics = _get_owner_pics_for_ratings(ratings)
    percent_map = _build_percent_map(ratings)
    rating_emoji_map = get_rating_emojis_for_rating_keys([r[0] for r in ratings])
    subject_emojis = get_top_subject_rating_emojis(
        mbid=mbid,
        rating_type=rating_type,
        rating_name=rating_name,
        content_artist=content_artist,
        limit=3,
    )

    return render_template(
        "also_rated.html",
        rating_key=rating_key,
        subject={
            "type": rating_type,
            "name": rating_name,
            "artist": content_artist,
        },
        artist_all_ratings_url=artist_all_ratings_url,
        summary=summary,
        ratings=ratings,
        active_tab=active_tab,
        tab_urls=tab_urls,
        owner_pics=owner_pics,
        percent_map=percent_map,
        rating_emoji_map=rating_emoji_map,
        subject_emojis=subject_emojis,
        pagination=_pagination_context(
            page=page,
            per_page=per_page,
            has_next=has_next,
            item_count=len(ratings),
        ),
    )


@app.route("/also-rated")
def also_rated_subject():
    raw_kind = (request.args.get("kind") or "").strip().lower()
    kind = raw_kind if raw_kind in {"song", "album", "artist"} else ""
    rating_type = {"song": "Song", "album": "Album", "artist": "Artist"}.get(kind)
    mbid = (request.args.get("mbid") or "").strip() or None
    rating_name = (request.args.get("name") or "").strip()
    content_artist = (request.args.get("artist") or "").strip() or None
    artist_all_ratings_url = None

    if not rating_type:
        flash("Invalid type.", "error")
        return redirect("/analytics")

    if not rating_name and not mbid:
        flash("Missing subject.", "error")
        return redirect("/analytics")

    if kind == "artist":
        content_artist = None
        rating_name = strip_artist_features(rating_name)
    elif kind in {"song", "album"} and content_artist:
        primary_artist = strip_artist_features(content_artist)
        artist_all_ratings_url = "/also-rated?" + urlencode(
            {"kind": "artist", "name": str(primary_artist or content_artist)}
        )

    summary = get_subject_overall_summary(
        mbid=mbid,
        rating_type=rating_type,
        rating_name=rating_name,
        content_artist=content_artist,
    )

    allowed_tabs = {"all", "artist", "albums", "songs"}
    raw_tab = (request.args.get("tab") or "all").strip().lower()
    active_tab = raw_tab if raw_tab in allowed_tabs else "all"
    if kind != "artist":
        active_tab = "all"

    page, per_page, offset = _parse_pagination(default_per_page=20)
    limit = per_page + 1

    if kind == "artist":
        raw_ratings = get_ratings_for_artist_including_works(
            artist_name=rating_name,
            scope=active_tab,
            limit=limit,
            offset=offset,
            order="recent",
        )
    else:
        raw_ratings = get_ratings_for_subject(
            exclude_rating_key=0,
            mbid=mbid,
            rating_type=rating_type,
            rating_name=rating_name,
            content_artist=content_artist,
            limit=limit,
            offset=offset,
            order="recent",
        )

    if kind == "artist" and summary:
        fetched = _cached_artist_image_url(artist_name=rating_name, artist_mbid=mbid)
        if fetched:
            summary["image_url"] = fetched

    has_next = len(raw_ratings) > per_page
    ratings = raw_ratings[:per_page]

    tab_urls = None
    if kind == "artist":
        base = "/also-rated"
        common_params: dict[str, str] = {"kind": "artist"}
        if mbid:
            common_params["mbid"] = str(mbid)
        if rating_name:
            common_params["name"] = str(rating_name)
        if per_page:
            common_params["per_page"] = str(int(per_page))

        tab_urls = {}
        for t in ("all", "artist", "albums", "songs"):
            params = dict(common_params)
            if t != "all":
                params["tab"] = t
            tab_urls[t] = base + "?" + urlencode(params)
    owner_pics = _get_owner_pics_for_ratings(ratings)
    percent_map = _build_percent_map(ratings)
    rating_emoji_map = get_rating_emojis_for_rating_keys([r[0] for r in ratings])
    subject_emojis = get_top_subject_rating_emojis(
        mbid=mbid,
        rating_type=rating_type,
        rating_name=rating_name,
        content_artist=content_artist,
        limit=3,
    )

    return render_template(
        "also_rated.html",
        rating_key=None,
        subject={
            "type": rating_type,
            "name": rating_name,
            "artist": content_artist,
        },
        artist_all_ratings_url=artist_all_ratings_url,
        summary=summary,
        ratings=ratings,
        active_tab=active_tab,
        tab_urls=tab_urls,
        owner_pics=owner_pics,
        percent_map=percent_map,
        rating_emoji_map=rating_emoji_map,
        subject_emojis=subject_emojis,
        pagination=_pagination_context(
            page=page,
            per_page=per_page,
            has_next=has_next,
            item_count=len(ratings),
        ),
    )


@app.route("/rating/<int:rating_key>/reactions/toggle", methods=["POST"])
@login_required
def rating_toggle_reaction(rating_key: int):
    rating = get_rating_by_key(rating_key)
    if not rating:
        return jsonify({"ok": False, "error": "Rating not found"}), 404

    payload = request.get_json(silent=True) or {}
    category = (payload.get("category") or "").strip()
    emoji = (payload.get("emoji") or "").strip()

    allowed_categories = {"Lyrics", "Beat", "Flow", "Melody", "Cohesive"}
    if category not in allowed_categories:
        return jsonify({"ok": False, "error": "Invalid category"}), 400

    if emoji not in set(REACTION_EMOJIS):
        return jsonify({"ok": False, "error": "Invalid emoji"}), 400

    is_present = toggle_rating_reaction(
        rating_key,
        current_user.id,
        category=category,
        emoji=emoji,
    )

    if is_present and not activity_exists(
        actor_user_id=current_user.id,
        action="rating_reaction",
        entity_type="rating",
        entity_id=rating_key,
    ):
        rating_type = (rating[1] or "").strip()
        rating_name = (rating[2] or "").strip()
        add_activity(
            current_user.id,
            current_user.username,
            action="rating_reaction",
            category=_category_from_rating_type(rating_type),
            entity_type="rating",
            entity_id=rating_key,
            entity_label=f"{rating_type}: {rating_name}".strip(": "),
            url=f"/rating/{rating_key}",
            metadata={"detail": category, "emoji": emoji},
        )

    summary = get_rating_reactions_summary(rating_key).get(category, [])
    mine = get_user_rating_reactions(rating_key, current_user.id).get(category, set())
    reactions_out = []
    for item in summary:
        em = (item.get("emoji") or "").strip()
        if not em:
            continue
        reactions_out.append(
            {
                "emoji": em,
                "count": int(item.get("count") or 0),
                "me": em in mine,
            }
        )

    return jsonify({"ok": True, "category": category, "reactions": reactions_out})


@app.route("/rating/<int:rating_key>/category-vote", methods=["POST"])
@login_required
def rating_category_vote(rating_key: int):
    rating = get_rating_by_key(rating_key)
    if not rating:
        if (request.headers.get("X-Requested-With") or "").lower() == "fetch":
            return jsonify({"ok": False, "error": "Rating not found"}), 404
        return redirect(f"/rating/{rating_key}")

    category = (request.form.get("category") or "").strip()
    direction = (request.form.get("direction") or "").strip().lower()

    allowed = {"Lyrics", "Beat", "Flow", "Melody", "Cohesive"}
    if category not in allowed:
        if (request.headers.get("X-Requested-With") or "").lower() == "fetch":
            return jsonify({"ok": False, "error": "Invalid category"}), 400
        flash("Invalid category.", "error")
        return _redirect_back(f"/rating/{rating_key}")

    vote = 0
    if direction == "up":
        vote = 1
    elif direction == "down":
        vote = -1
    else:
        if (request.headers.get("X-Requested-With") or "").lower() == "fetch":
            return jsonify({"ok": False, "error": "Invalid vote"}), 400
        flash("Invalid vote.", "error")
        return _redirect_back(f"/rating/{rating_key}")

    current_votes = get_user_rating_category_votes(rating_key, current_user.id)
    current_vote = int(current_votes.get(category) or 0)

    if current_vote == 0:
        new_vote = vote
    elif current_vote == vote:
        new_vote = 0
    else:
        new_vote = 0

    set_rating_category_vote(rating_key, current_user.id, category, new_vote)

    rating_type = (rating[1] or "").strip()
    rating_name = (rating[2] or "").strip()
    add_activity(
        current_user.id,
        current_user.username,
        action=(
            "rating_category_unvote"
            if new_vote == 0
            else (
                "rating_category_upvote"
                if new_vote == 1
                else "rating_category_downvote"
            )
        ),
        category=_category_from_rating_type(rating_type),
        entity_type="rating",
        entity_id=rating_key,
        entity_label=f"{rating_type}: {rating_name}".strip(": "),
        url=f"/rating/{rating_key}",
        metadata={"detail": category},
    )

    if (request.headers.get("X-Requested-With") or "").lower() == "fetch":
        summary = get_rating_category_votes_summary(rating_key).get(category, {}) or {}
        mine = int(
            (
                get_user_rating_category_votes(rating_key, current_user.id).get(
                    category
                )
                or 0
            )
        )
        return jsonify(
            {
                "ok": True,
                "category": category,
                "score": int(summary.get("score") or 0),
                "mine": mine,
            }
        )

    return _redirect_back(f"/rating/{rating_key}")


@app.route("/rating/<int:rating_key>/like", methods=["POST"])
@login_required
def toggle_like_rating(rating_key: int):
    rating = get_rating_by_key(rating_key)
    if not rating:
        return redirect("/browse")

    new_liked = toggle_rating_like(rating_key, current_user.id)

    rating_type = (rating[1] or "").strip()
    rating_name = (rating[2] or "").strip()
    add_activity(
        current_user.id,
        current_user.username,
        action="rating_like" if new_liked else "rating_unlike",
        category=_category_from_rating_type(rating_type),
        entity_type="rating",
        entity_id=rating_key,
        entity_label=f"{rating_type}: {rating_name}".strip(": "),
        url=f"/rating/{rating_key}",
    )

    return _redirect_back(f"/rating/{rating_key}")


def _build_rating_comments(rating_key: int) -> list[dict]:
    stored_comments = get_rating_comments(rating_key)
    display_comments = []
    for comment in stored_comments:
        profile_pic = comment.get("profile_pic")
        if profile_pic and not _pic_exists(profile_pic):
            profile_pic = None
        display_comments.append(
            {
                "comment_id": comment.get("comment_id"),
                "message": comment.get("message", ""),
                "username": comment.get("username"),
                "profile_pic": profile_pic,
                "author_user_id": comment.get("author_user_id"),
                "time_ago": _format_time_ago(comment.get("created_at")),
            }
        )
    return display_comments


@app.route("/rating/<int:rating_key>/comments", methods=["POST"])
@login_required
def add_rating_comment_route(rating_key: int):
    rating = get_rating_by_key(rating_key)
    if not rating:
        flash("Rating not found.", "error")
        return redirect("/browse")

    message = (request.form.get("comment") or "").strip()
    if not message:
        return _redirect_back(f"/rating/{rating_key}", fragment="comments")

    created_at = datetime.now(timezone.utc).isoformat()
    add_rating_comment(rating_key, current_user.id, message, created_at)

    rating_type = (rating[1] or "").strip()
    rating_name = (rating[2] or "").strip()
    category = _category_from_rating_type(rating_type)
    add_activity(
        current_user.id,
        current_user.username,
        action="rating_comment_add",
        category=category,
        entity_type="rating",
        entity_id=rating_key,
        entity_label=f"{rating_type}: {rating_name}".strip(": "),
        url=f"/rating/{rating_key}",
        metadata={"message_length": len(message)},
        created_at=created_at,
    )

    owner_username = get_rating_owner(rating_key)
    owner_user = get_user_by_username(owner_username) if owner_username else None
    if owner_user and owner_user.id != current_user.id:
        create_alert(
            owner_user.id,
            f"{current_user.username} commented on your rating",
            f"/rating/{rating_key}#comments",
            created_at,
        )

    return _redirect_back(f"/rating/{rating_key}", fragment="comments")


@app.route("/rating/<int:rating_key>/comments/edit/<int:comment_id>", methods=["POST"])
@login_required
def edit_rating_comment_route(rating_key: int, comment_id: int):
    rating = get_rating_by_key(rating_key)
    comment = get_rating_comment(comment_id)
    if (
        not rating
        or not comment
        or int(comment.get("rating_key") or 0) != int(rating_key)
    ):
        flash("Comment not found.", "error")
        return _redirect_back(f"/rating/{rating_key}", fragment="comments")

    message = (request.form.get("comment") or "").strip()
    if not message:
        return _redirect_back(f"/rating/{rating_key}", fragment="comments")

    updated = update_rating_comment(comment_id, current_user.id, message)
    if not updated:
        flash("You can only edit your own comments.", "error")
        return _redirect_back(f"/rating/{rating_key}", fragment="comments")

    rating_type = (rating[1] or "").strip()
    rating_name = (rating[2] or "").strip()
    add_activity(
        current_user.id,
        current_user.username,
        action="rating_comment_edit",
        category=_category_from_rating_type(rating_type),
        entity_type="comment",
        entity_id=comment_id,
        entity_label=f"{rating_type}: {rating_name}".strip(": "),
        url=f"/rating/{rating_key}",
        metadata={"message_length": len(message)},
    )

    return _redirect_back(f"/rating/{rating_key}", fragment="comments")


@app.route(
    "/rating/<int:rating_key>/comments/delete/<int:comment_id>", methods=["POST"]
)
@login_required
def delete_rating_comment_route(rating_key: int, comment_id: int):
    rating = get_rating_by_key(rating_key)
    comment = get_rating_comment(comment_id)
    if (
        not rating
        or not comment
        or int(comment.get("rating_key") or 0) != int(rating_key)
    ):
        flash("Comment not found.", "error")
        return _redirect_back(f"/rating/{rating_key}", fragment="comments")

    deleted = delete_rating_comment(comment_id, current_user.id)
    if not deleted:
        flash("You can only delete your own comments.", "error")
        return _redirect_back(f"/rating/{rating_key}", fragment="comments")

    rating_type = (rating[1] or "").strip()
    rating_name = (rating[2] or "").strip()
    add_activity(
        current_user.id,
        current_user.username,
        action="rating_comment_delete",
        category=_category_from_rating_type(rating_type),
        entity_type="comment",
        entity_id=comment_id,
        entity_label=f"{rating_type}: {rating_name}".strip(": "),
        url=f"/rating/{rating_key}",
    )

    return _redirect_back(f"/rating/{rating_key}", fragment="comments")


# Add a new rating
@app.route("/add", methods=["GET", "POST"])
@login_required
def add():
    if request.method == "POST":
        rating_type = request.form.get("rating_type", "").strip()
        rating_name = request.form.get("rating_name", "").strip()
        rating_emoji = (request.form.get("rating_emoji") or "").strip()
        mbid = (request.form.get("mbid") or "").strip()
        mb_url = (request.form.get("mb_url") or "").strip()
        content_artist = (request.form.get("content_artist") or "").strip()
        extra_link = (request.form.get("extra_link") or "").strip()
        extra_info = (request.form.get("extra_info") or "").strip()
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

        # Uploaded artwork/cover image
        uploaded_image = request.files.get("rating_image")
        rating_image_url = None

        missing = []
        if not rating_type:
            missing.append("Rating Type")
        if not rating_name:
            missing.append("Name")
        if not rating_emoji:
            missing.append("Emoji")
        if not lyrics_rating:
            missing.append("Lyrics")
        if not beat_rating:
            missing.append("Beat")
        if not flow_rating:
            missing.append("Flow")
        if not melody_rating:
            missing.append("Melody")
        if not cohesive_rating:
            missing.append("Cohesive")

        if missing:
            session["add_form_draft"] = {
                "rating_type": rating_type,
                "rating_name": rating_name,
                "rating_emoji": rating_emoji,
                "mbid": mbid,
                "mb_url": mb_url,
                "content_artist": content_artist,
                "extra_link": extra_link,
                "extra_info": extra_info,
                "lyrics": lyrics_rating,
                "lyrics_reason": lyrics_reason,
                "beat": beat_rating,
                "beat_reason": beat_reason,
                "flow": flow_rating,
                "flow_reason": flow_reason,
                "melody": melody_rating,
                "melody_reason": melody_reason,
                "cohesive": cohesive_rating,
                "cohesive_reason": cohesive_reason,
            }
            flash(
                "Please complete the rating before submitting.\nMissing: "
                + ", ".join(missing),
                "error",
            )
            return redirect("/add")

        if uploaded_image and uploaded_image.filename:
            if not _allowed_file(uploaded_image.filename):
                session["add_form_draft"] = {
                    "rating_type": rating_type,
                    "rating_name": rating_name,
                    "rating_emoji": rating_emoji,
                    "mbid": mbid,
                    "mb_url": mb_url,
                    "content_artist": content_artist,
                    "extra_link": extra_link,
                    "extra_info": extra_info,
                    "lyrics": lyrics_rating,
                    "lyrics_reason": lyrics_reason,
                    "beat": beat_rating,
                    "beat_reason": beat_reason,
                    "flow": flow_rating,
                    "flow_reason": flow_reason,
                    "melody": melody_rating,
                    "melody_reason": melody_reason,
                    "cohesive": cohesive_rating,
                    "cohesive_reason": cohesive_reason,
                }
                flash("Unsupported image file type.", "error")
                return redirect("/add")

            upload_root = Path(current_app.config.get("UPLOAD_FOLDER"))
            ratings_folder = upload_root / "ratings"
            ratings_folder.mkdir(parents=True, exist_ok=True)

            ext = uploaded_image.filename.rsplit(".", 1)[1].lower()
            unique = uuid.uuid4().hex
            base = secure_filename(rating_name) or "rating"
            filename = secure_filename(
                f"rating_{current_user.id}_{unique}_{base}.{ext}"
            )
            save_path = ratings_folder / filename
            uploaded_image.save(str(save_path))

            url_prefix = (
                current_app.config.get("UPLOAD_URL_PREFIX") or "/uploads"
            ).rstrip("/")
            rating_image_url = f"{url_prefix}/ratings/{filename}"

        if not rating_image_url and mbid:
            rt = (rating_type or "").strip().lower()
            if rt == "album":
                rating_image_url = _cover_art_url_for_release_group(mbid) or None
            elif rt == "song":
                rating_image_url = _cover_art_url_for_recording(mbid) or None
            elif rt == "artist":
                rating_image_url = _artist_image_url(mbid) or None

        if rating_type:
            rating_key = add_rating(
                rating_type,
                rating_name,
                rating_emoji or None,
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
                current_user.username,
                rating_image_url,
                mbid or None,
                mb_url or None,
                content_artist or None,
                extra_link or None,
                extra_info or None,
            )
            category = _category_from_rating_type(rating_type)
            add_activity(
                current_user.id,
                current_user.username,
                action="rating_create",
                category=category,
                entity_type="rating",
                entity_id=rating_key,
                entity_label=f"{rating_type}: {rating_name}".strip(": "),
                url=f"/rating/{rating_key}" if rating_key else "/browse",
            )
        session.pop("add_form_draft", None)
        return redirect("/browse")

    draft = session.pop("add_form_draft", None)
    return render_template(
        "add.html",
        form_action="/add",
        draft=draft or {},
        reaction_emojis=REACTION_EMOJIS,
    )


def _build_profile_comments(profile_user_id):
    stored_comments = get_profile_comments_db(profile_user_id)
    display_comments = []
    for comment in stored_comments:
        profile_pic = comment.get("profile_pic")
        if profile_pic and not _pic_exists(profile_pic):
            profile_pic = None
        display_comments.append(
            {
                "comment_id": comment.get("comment_id"),
                "message": comment.get("message", ""),
                "username": comment.get("username"),
                "profile_pic": profile_pic,
                "author_user_id": comment.get("author_user_id"),
                "time_ago": _format_time_ago(comment.get("created_at")),
            }
        )
    return display_comments


# Profile page
@app.route("/profile", methods=["GET"])
@login_required
def profile():
    return _render_profile(current_user)


@app.route("/user/<username>", methods=["GET"])
@login_required
def user_profile(username):
    user = get_user_by_username(username)
    if not user:
        return redirect("/browse")
    return _render_profile(user)


@app.route("/user/<username>/follow", methods=["POST"])
@login_required
def follow(username):
    user = get_user_by_username(username)
    if not user or user.id == current_user.id:
        return _redirect_back("/profile")
    already_following = is_following(user.id, current_user.id)
    follow_user(user.id, current_user.id)
    if not already_following:
        create_alert(
            user.id,
            f"{current_user.username} followed you",
            f"/user/{current_user.username}",
        )
        add_activity(
            current_user.id,
            current_user.username,
            action="follow",
            category="users",
            entity_type="user",
            entity_id=user.id,
            entity_label=f"@{user.username}",
            url=f"/user/{user.username}",
        )
    follow_tab = request.form.get("follow_tab")
    if follow_tab in {"followers", "following"}:
        return redirect(f"/user/{username}?follow_tab={follow_tab}")
    return _redirect_back(f"/user/{username}")


@app.route("/user/<username>/unfollow", methods=["POST"])
@login_required
def unfollow(username):
    user = get_user_by_username(username)
    if not user or user.id == current_user.id:
        return _redirect_back("/profile")
    was_following = is_following(user.id, current_user.id)
    unfollow_user(user.id, current_user.id)
    if was_following:
        add_activity(
            current_user.id,
            current_user.username,
            action="unfollow",
            category="users",
            entity_type="user",
            entity_id=user.id,
            entity_label=f"@{user.username}",
            url=f"/user/{user.username}",
        )
    follow_tab = request.form.get("follow_tab")
    if follow_tab in {"followers", "following"}:
        return redirect(f"/user/{username}?follow_tab={follow_tab}")
    return _redirect_back(f"/user/{username}")


def _render_profile(profile_user):
    if profile_user.profile_pic and not _pic_exists(profile_user.profile_pic):
        profile_user.profile_pic = None
    comments = _build_profile_comments(profile_user.id)
    profile_ratings = get_ratings_by_user(profile_user.username)
    profile_percent_map = _build_percent_map(profile_ratings)
    favorite_ratings = get_liked_ratings_for_user(profile_user.id, limit=60)
    favorite_percent_map = _build_percent_map(favorite_ratings)
    profile_playlists = get_playlists_by_creator(profile_user.username, limit=200)
    is_owner = current_user.is_authenticated and current_user.id == profile_user.id
    active_follow_tab = request.args.get("follow_tab")
    active_profile_tab = request.args.get("profile_tab")
    if active_profile_tab not in {"ratings", "playlists", "favorites"}:
        active_profile_tab = "ratings"
    follower_count = count_followers(profile_user.id)
    following_count = count_following(profile_user.id)
    following = get_following(profile_user.id, limit=10, offset=0)
    followers = get_followers(profile_user.id, limit=10, offset=0)
    viewer_follows = (
        current_user.is_authenticated
        and not is_owner
        and is_following(profile_user.id, current_user.id)
    )
    return render_template(
        "profile.html",
        profile_user=profile_user,
        comments=comments,
        profile_ratings=profile_ratings,
        profile_percent_map=profile_percent_map,
        profile_playlists=profile_playlists,
        favorite_ratings=favorite_ratings,
        favorite_percent_map=favorite_percent_map,
        is_owner=is_owner,
        active_follow_tab=active_follow_tab,
        active_profile_tab=active_profile_tab,
        following=following,
        followers=followers,
        follower_count=follower_count,
        following_count=following_count,
        viewer_follows=viewer_follows,
    )


@app.route("/user/<username>/following", methods=["GET"])
@login_required
def user_following_page(username: str):
    profile_user = get_user_by_username(username)
    if not profile_user:
        flash("User not found.", "error")
        return redirect("/")

    page, per_page, offset = _parse_pagination()
    follower_count = count_followers(profile_user.id)
    following_count = count_following(profile_user.id)
    raw_users = get_following(profile_user.id, limit=per_page + 1, offset=offset)
    has_next = len(raw_users) > per_page
    users = raw_users[:per_page]

    return render_template(
        "follows.html",
        title=f"@{profile_user.username}",
        profile_user=profile_user,
        active_tab="following",
        users=users,
        follower_count=follower_count,
        following_count=following_count,
        total_count=following_count,
        empty_text="Not following anyone yet.",
        pagination=_pagination_context(
            page=page,
            per_page=per_page,
            has_next=has_next,
            item_count=following_count,
        ),
    )


@app.route("/user/<username>/followers", methods=["GET"])
@login_required
def user_followers_page(username: str):
    profile_user = get_user_by_username(username)
    if not profile_user:
        flash("User not found.", "error")
        return redirect("/")

    page, per_page, offset = _parse_pagination()
    follower_count = count_followers(profile_user.id)
    following_count = count_following(profile_user.id)
    raw_users = get_followers(profile_user.id, limit=per_page + 1, offset=offset)
    has_next = len(raw_users) > per_page
    users = raw_users[:per_page]

    return render_template(
        "follows.html",
        title=f"@{profile_user.username}",
        profile_user=profile_user,
        active_tab="followers",
        users=users,
        follower_count=follower_count,
        following_count=following_count,
        total_count=follower_count,
        empty_text="No followers yet.",
        pagination=_pagination_context(
            page=page,
            per_page=per_page,
            has_next=has_next,
            item_count=follower_count,
        ),
    )


@app.route("/user/<username>/ratings", methods=["GET"])
@login_required
def user_ratings_page(username: str):
    profile_user = get_user_by_username(username)
    if not profile_user:
        flash("User not found.", "error")
        return redirect("/")

    page, per_page, offset = _parse_pagination()
    raw_ratings = get_ratings_by_user_paginated(
        profile_user.username, limit=per_page + 1, offset=offset
    )
    has_next = len(raw_ratings) > per_page
    ratings = raw_ratings[:per_page]
    percent_map = _build_percent_map(ratings)
    pagination = _pagination_context(
        page=page,
        per_page=per_page,
        has_next=has_next,
        item_count=len(ratings),
    )

    return render_template(
        "profile_media.html",
        title=f"@{profile_user.username}",
        profile_user=profile_user,
        active_tab="ratings",
        ratings=ratings,
        playlists=[],
        favorites=[],
        percent_map=percent_map,
        empty_text="No ratings yet.",
        pagination=pagination,
    )


@app.route("/user/<username>/playlists", methods=["GET"])
@login_required
def user_playlists_page(username: str):
    profile_user = get_user_by_username(username)
    if not profile_user:
        flash("User not found.", "error")
        return redirect("/")

    page, per_page, offset = _parse_pagination()
    raw_playlists = get_playlists_by_creator(
        profile_user.username, limit=per_page + 1, offset=offset
    )
    has_next = len(raw_playlists) > per_page
    playlists = raw_playlists[:per_page]
    pagination = _pagination_context(
        page=page,
        per_page=per_page,
        has_next=has_next,
        item_count=len(playlists),
    )

    return render_template(
        "profile_media.html",
        title=f"@{profile_user.username}",
        profile_user=profile_user,
        active_tab="playlists",
        ratings=[],
        playlists=playlists,
        favorites=[],
        percent_map={},
        empty_text="No playlists yet.",
        pagination=pagination,
    )


@app.route("/user/<username>/favorites", methods=["GET"])
@login_required
def user_favorites_page(username: str):
    profile_user = get_user_by_username(username)
    if not profile_user:
        flash("User not found.", "error")
        return redirect("/")

    page, per_page, offset = _parse_pagination()
    raw_favorites = get_liked_ratings_for_user(
        profile_user.id, limit=per_page + 1, offset=offset
    )
    has_next = len(raw_favorites) > per_page
    favorites = raw_favorites[:per_page]
    percent_map = _build_percent_map(favorites)
    pagination = _pagination_context(
        page=page,
        per_page=per_page,
        has_next=has_next,
        item_count=len(favorites),
    )

    return render_template(
        "profile_media.html",
        title=f"@{profile_user.username}",
        profile_user=profile_user,
        active_tab="favorites",
        ratings=[],
        playlists=[],
        favorites=favorites,
        percent_map=percent_map,
        empty_text="No favorites yet.",
        pagination=pagination,
    )


# profile-edit
@app.route("/profile-edit", methods=["GET", "POST"])
@login_required
def profile_edit():
    if current_user.profile_pic and not _pic_exists(current_user.profile_pic):
        current_user.profile_pic = None
    if request.method == "POST":
        username = request.form.get("username_edit", "").strip()
        about = request.form.get("about", "").strip()
        updated_username = username if username else current_user.username
        updated_about = about if about else current_user.about
        if (
            updated_username != current_user.username
            or updated_about != current_user.about
        ):
            update_profile_info(current_user.id, updated_username, updated_about)
            current_user.username = updated_username
            current_user.about = updated_about
            add_activity(
                current_user.id,
                current_user.username,
                action="profile_update",
                category="users",
                entity_type="user",
                entity_id=current_user.id,
                entity_label=f"@{current_user.username}",
                url="/profile",
            )
        return redirect("/profile")
    return render_template("profile-edit.html")


# edit-profile
@app.route("/edit-profile", methods=["GET", "POST"])
@login_required
def edit_profile():
    return profile_edit()


# Upload new profile picture
@app.route("/profile/upload", methods=["POST"])
@login_required
def upload_profile_pic():
    file = request.files.get("profile_pic")
    if not file or file.filename == "":
        flash("No file selected.", "profile")
        return redirect("/profile-edit")
    if not _allowed_file(file.filename):
        flash("Unsupported file type.", "profile")
        return redirect("/profile-edit")

    upload_folder = Path(current_app.config.get("UPLOAD_FOLDER"))
    upload_folder.mkdir(parents=True, exist_ok=True)

    ext = file.filename.rsplit(".", 1)[1].lower()
    filename = secure_filename(f"user_{current_user.id}.{ext}")
    save_path = upload_folder / filename
    file.save(str(save_path))

    url_prefix = (current_app.config.get("UPLOAD_URL_PREFIX") or "/uploads").rstrip("/")
    rel_path = f"{url_prefix}/{filename}"
    update_profile_pic(current_user.id, rel_path)
    add_activity(
        current_user.id,
        current_user.username,
        action="profile_update",
        category="users",
        entity_type="user",
        entity_id=current_user.id,
        entity_label=f"@{current_user.username}",
        url="/profile-edit",
    )
    flash("Profile picture updated.", "profile")
    return redirect("/profile-edit")


# Remove the user's profile picture
@app.route("/profile/remove", methods=["POST"])
@login_required
def remove_profile_pic():
    update_profile_pic(current_user.id, None)
    add_activity(
        current_user.id,
        current_user.username,
        action="profile_update",
        category="users",
        entity_type="user",
        entity_id=current_user.id,
        entity_label=f"@{current_user.username}",
        url="/profile-edit",
    )
    flash("Profile picture removed.", "profile")
    return redirect("/profile-edit")


# Add profile comment
@app.route("/profile/comments", methods=["POST"])
@login_required
def add_profile_comment():
    message = request.form.get("comment", "").strip()
    profile_user_id = request.form.get("profile_user_id", type=int)
    if not message:
        return _redirect_back("/profile", fragment="comments")

    target_user_id = profile_user_id or current_user.id
    if not get_user_by_id(target_user_id):
        return redirect("/profile")

    created_at = datetime.now(timezone.utc).isoformat()
    add_profile_comment_db(
        target_user_id,
        current_user.id,
        message,
        created_at,
    )

    target_user = get_user_by_id(target_user_id)
    target_label = f"@{target_user.username}" if target_user else "a profile"
    target_url = (
        (
            "/profile"
            if target_user_id == current_user.id
            else f"/user/{target_user.username}"
        )
        if target_user
        else "/profile"
    )
    add_activity(
        current_user.id,
        current_user.username,
        action="profile_comment_add",
        category="users",
        entity_type="user",
        entity_id=target_user_id,
        entity_label=target_label,
        url=target_url,
        metadata={"message_length": len(message)},
        created_at=created_at,
    )
    if target_user_id != current_user.id:
        create_alert(
            target_user_id,
            f"{current_user.username} commented on your profile",
            "/profile#comments",
            created_at,
        )

    default_path = "/profile"
    if profile_user_id and profile_user_id != current_user.id:
        user = get_user_by_id(profile_user_id)
        if user:
            default_path = f"/user/{user.username}"
    return _redirect_back(default_path, fragment="comments")


# Delete profile comment
@app.route("/profile/comments/delete/<int:comment_id>", methods=["POST"])
@login_required
def delete_profile_comment(comment_id):
    delete_profile_comment_db(comment_id, current_user.id)
    add_activity(
        current_user.id,
        current_user.username,
        action="profile_comment_delete",
        category="users",
        entity_type="comment",
        entity_id=comment_id,
        entity_label="a profile",
        url=_safe_internal_url(request.referrer, "/profile"),
    )
    return _redirect_back("/profile", fragment="comments")


# Edit profile comment
@app.route("/profile/comments/edit/<int:comment_id>", methods=["POST"])
@login_required
def edit_profile_comment(comment_id):
    message = request.form.get("comment", "").strip()
    if message:
        update_profile_comment_db(comment_id, current_user.id, message)
        add_activity(
            current_user.id,
            current_user.username,
            action="profile_comment_edit",
            category="users",
            entity_type="comment",
            entity_id=comment_id,
            entity_label="a profile",
            url=_safe_internal_url(request.referrer, "/profile"),
            metadata={"message_length": len(message)},
        )
    return _redirect_back("/profile", fragment="comments")


# Edit rating
@app.route("/edit/<int:rating_key>", methods=["GET", "POST"])
@login_required
def edit(rating_key):
    owner = get_rating_owner(rating_key)
    if not owner or owner != current_user.username:
        flash("You can only edit your own ratings.", "error")
        return redirect("/browse")
    rating = get_rating_by_key(rating_key)
    if not rating:
        return redirect("/browse")

    current_extra_link, current_extra_info = get_rating_extras_by_key(rating_key)

    if request.method == "POST":
        current_rating_type = (rating[1] or "").strip()
        current_rating_name = (rating[2] or "").strip()
        current_lyrics_rating = rating[3]
        current_lyrics_reason = (rating[4] or "").strip()
        current_beat_rating = rating[5]
        current_beat_reason = (rating[6] or "").strip()
        current_flow_rating = rating[7]
        current_flow_reason = (rating[8] or "").strip()
        current_melody_rating = rating[9]
        current_melody_reason = (rating[10] or "").strip()
        current_cohesive_rating = rating[11]
        current_cohesive_reason = (rating[12] or "").strip()
        current_image_url = rating[-1] if len(rating) > 13 else None
        current_mbid = (rating[-4] if len(rating) > 16 else None) or None
        current_mb_url = (rating[-3] if len(rating) > 16 else None) or None
        current_content_artist = (rating[-2] if len(rating) > 14 else None) or None

        rating_type = request.form.get("rating_type", "").strip()
        rating_name = request.form.get("rating_name", "").strip()
        mbid = (request.form.get("mbid") or "").strip() or None
        mb_url = (request.form.get("mb_url") or "").strip() or None
        content_artist = (request.form.get("content_artist") or "").strip() or None
        extra_link = (request.form.get("extra_link") or "").strip() or None
        extra_info = (request.form.get("extra_info") or "").strip() or None
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
        uploaded_image = request.files.get("rating_image")
        remove_current_image = (
            request.form.get("remove_rating_image") or ""
        ).strip() == "1"
        rating_image_url = current_image_url

        if remove_current_image:
            rating_image_url = None

        if uploaded_image and uploaded_image.filename:
            if not _allowed_file(uploaded_image.filename):
                flash("Unsupported image file type.", "error")
                return redirect(f"/edit/{rating_key}")

            upload_root = Path(current_app.config.get("UPLOAD_FOLDER"))
            ratings_folder = upload_root / "ratings"
            ratings_folder.mkdir(parents=True, exist_ok=True)

            ext = uploaded_image.filename.rsplit(".", 1)[1].lower()
            unique = uuid.uuid4().hex
            base = secure_filename(rating_name) or "rating"
            filename = secure_filename(
                f"rating_{current_user.id}_{unique}_{base}.{ext}"
            )
            save_path = ratings_folder / filename
            uploaded_image.save(str(save_path))
            url_prefix = (
                current_app.config.get("UPLOAD_URL_PREFIX") or "/uploads"
            ).rstrip("/")
            rating_image_url = f"{url_prefix}/ratings/{filename}"

        if not rating_image_url and mbid:
            rt = (rating_type or "").strip().lower()
            if rt == "album":
                rating_image_url = _cover_art_url_for_release_group(mbid) or None
            elif rt == "song":
                rating_image_url = _cover_art_url_for_recording(mbid) or None
            elif rt == "artist":
                rating_image_url = _artist_image_url(mbid) or None

        def _to_int(v):
            try:
                return int(v)
            except (TypeError, ValueError):
                return None

        did_change = any(
            [
                rating_type != current_rating_type,
                rating_name != current_rating_name,
                _to_int(lyrics_rating) != _to_int(current_lyrics_rating),
                (lyrics_reason or "").strip() != current_lyrics_reason,
                _to_int(beat_rating) != _to_int(current_beat_rating),
                (beat_reason or "").strip() != current_beat_reason,
                _to_int(flow_rating) != _to_int(current_flow_rating),
                (flow_reason or "").strip() != current_flow_reason,
                _to_int(melody_rating) != _to_int(current_melody_rating),
                (melody_reason or "").strip() != current_melody_reason,
                _to_int(cohesive_rating) != _to_int(current_cohesive_rating),
                (cohesive_reason or "").strip() != current_cohesive_reason,
                (rating_image_url or None) != (current_image_url or None),
                (mbid or None) != (current_mbid or None),
                (mb_url or None) != (current_mb_url or None),
                (content_artist or None) != (current_content_artist or None),
                (extra_link or None) != (current_extra_link or None),
                (extra_info or None) != (current_extra_info or None),
            ]
        )

        if not did_change:
            return redirect(f"/rating/{rating_key}")

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
                rating_image_url,
                mbid,
                mb_url,
                content_artist,
                extra_link,
                extra_info,
            )
            category = _category_from_rating_type(rating_type)
            add_activity(
                current_user.id,
                current_user.username,
                action="rating_edit",
                category=category,
                entity_type="rating",
                entity_id=rating_key,
                entity_label=f"{rating_type}: {rating_name}".strip(": "),
                url=f"/rating/{rating_key}",
            )
        return redirect(f"/rating/{rating_key}")
    return render_template(
        "edit.html",
        rating=rating,
        form_action=f"/edit/{rating_key}",
        extra_link=current_extra_link or "",
        extra_info=current_extra_info or "",
    )


# Delete rating
@app.route("/delete/<int:rating_key>", methods=["POST"])
@login_required
def delete(rating_key):
    owner = get_rating_owner(rating_key)
    if not owner or owner != current_user.username:
        flash("You can only delete your own ratings.", "error")
        return redirect("/browse")
    rating = get_rating_by_key(rating_key)
    rating_type = (rating[1] or "").strip() if rating else ""
    rating_name = (rating[2] or "").strip() if rating else ""
    delete_rating(rating_key)
    category = _category_from_rating_type(rating_type)
    add_activity(
        current_user.id,
        current_user.username,
        action="rating_delete",
        category=category,
        entity_type="rating",
        entity_id=rating_key,
        entity_label=f"{rating_type}: {rating_name}".strip(": "),
        url="/browse",
    )
    return redirect("/browse")


def _category_from_rating_type(rating_type: str) -> str:
    t = (rating_type or "").strip().lower()
    if not t:
        return "all"
    if "artist" in t:
        return "artists"
    if "album" in t:
        return "albums"
    if "song" in t or "track" in t:
        return "songs"
    if "genre" in t:
        return "genres"
    return "all"


###############################################
# MusicBrainz
###############################################

_MB_LAST_CALL_AT: float = 0.0
_MB_THROTTLE_LOCK = threading.Lock()

_CAA_LAST_CALL_AT: float = 0.0
_CAA_THROTTLE_LOCK = threading.Lock()

_WIKIDATA_LAST_CALL_AT: float = 0.0
_WIKIDATA_THROTTLE_LOCK = threading.Lock()


def _musicbrainz_user_agent() -> str:
    return (
        os.environ.get("MUSICBRAINZ_USER_AGENT")
        or "RealTop/1.0 (set MUSICBRAINZ_USER_AGENT; contact: required)"
    ).strip()


def _mb_throttle() -> None:
    # MusicBrainz rate limits
    global _MB_LAST_CALL_AT
    with _MB_THROTTLE_LOCK:
        try:
            min_interval = float(
                os.environ.get("MUSICBRAINZ_MIN_INTERVAL_SECONDS") or "1.0"
            )
        except ValueError:
            min_interval = 1.0
        min_interval = max(0.2, min(10.0, min_interval))
        now = time.time()
        wait = (_MB_LAST_CALL_AT + min_interval) - now
        if wait > 0:
            time.sleep(min(wait, min_interval + 0.25))
        _MB_LAST_CALL_AT = time.time()


def _caa_throttle() -> None:
    # Throttle for Cover Art Archive requests.
    global _CAA_LAST_CALL_AT
    with _CAA_THROTTLE_LOCK:
        try:
            min_interval = float(
                os.environ.get("COVERART_MIN_INTERVAL_SECONDS") or "1.0"
            )
        except ValueError:
            min_interval = 1.0
        min_interval = max(0.2, min(10.0, min_interval))
        now = time.time()
        wait = (_CAA_LAST_CALL_AT + min_interval) - now
        if wait > 0:
            time.sleep(min(wait, min_interval + 0.25))
        _CAA_LAST_CALL_AT = time.time()


@app.route("/image-proxy")
def image_proxy():
    raw_url = (request.args.get("url") or "").strip()
    if not _is_proxyable_image_url(raw_url):
        return ("", 404)

    parsed = urlsplit(raw_url)
    safe_url = urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.query,
            "",
        )
    )

    host = (parsed.netloc or "").split(":", 1)[0].strip().lower()
    headers = {
        "User-Agent": _musicbrainz_user_agent(),
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    }

    try:
        if host == "coverartarchive.org":
            _caa_throttle()
        resp = requests.get(safe_url, headers=headers, timeout=20)
    except requests.RequestException:
        return ("", 502)

    if resp.status_code != 200:
        return ("", resp.status_code)

    content_type = (resp.headers.get("Content-Type") or "application/octet-stream").strip()
    out = Response(resp.content, status=200, content_type=content_type)
    cache_control = resp.headers.get("Cache-Control")
    if cache_control:
        out.headers["Cache-Control"] = cache_control
    else:
        out.headers["Cache-Control"] = "public, max-age=86400"
    etag = resp.headers.get("ETag")
    if etag:
        out.headers["ETag"] = etag
    last_modified = resp.headers.get("Last-Modified")
    if last_modified:
        out.headers["Last-Modified"] = last_modified
    return out


def _wikidata_throttle() -> None:
    # Throttle for Wikidata requests.
    global _WIKIDATA_LAST_CALL_AT
    with _WIKIDATA_THROTTLE_LOCK:
        try:
            min_interval = float(
                os.environ.get("WIKIDATA_MIN_INTERVAL_SECONDS") or "1.0"
            )
        except ValueError:
            min_interval = 1.0
        min_interval = max(0.2, min(10.0, min_interval))
        now = time.time()
        wait = (_WIKIDATA_LAST_CALL_AT + min_interval) - now
        if wait > 0:
            time.sleep(min(wait, min_interval + 0.25))
        _WIKIDATA_LAST_CALL_AT = time.time()


def _cover_art_url_for_release_group(release_group_mbid: str) -> str | None:
    mbid = (release_group_mbid or "").strip()
    if not mbid:
        return None
    url = f"https://coverartarchive.org/release-group/{mbid}"
    headers = {"Accept": "application/json", "User-Agent": _musicbrainz_user_agent()}
    try:
        _caa_throttle()
        resp = requests.get(url, headers=headers, timeout=8)
    except requests.RequestException:
        return None
    if resp.status_code != 200:
        return None
    try:
        data = resp.json()
    except ValueError:
        return None
    images = data.get("images") or []
    if not images:
        return None
    preferred = None
    for img in images:
        if img.get("front"):
            preferred = img
            break
    preferred = preferred or images[0]
    thumbs = preferred.get("thumbnails") or {}
    return (
        thumbs.get("1200")
        or thumbs.get("500")
        or thumbs.get("250")
        or thumbs.get("large")
        or thumbs.get("small")
        or preferred.get("image")
        or None
    )


def _cover_art_url_for_release(release_mbid: str) -> str | None:
    mbid = (release_mbid or "").strip()
    if not mbid:
        return None
    url = f"https://coverartarchive.org/release/{mbid}"
    headers = {"Accept": "application/json", "User-Agent": _musicbrainz_user_agent()}
    try:
        _caa_throttle()
        resp = requests.get(url, headers=headers, timeout=8)
    except requests.RequestException:
        return None
    if resp.status_code != 200:
        return None
    try:
        data = resp.json()
    except ValueError:
        return None
    images = data.get("images") or []
    if not images:
        return None
    preferred = None
    for img in images:
        if img.get("front"):
            preferred = img
            break
    preferred = preferred or images[0]
    thumbs = preferred.get("thumbnails") or {}
    return (
        thumbs.get("1200")
        or thumbs.get("500")
        or thumbs.get("250")
        or thumbs.get("large")
        or thumbs.get("small")
        or preferred.get("image")
        or None
    )


def _cover_art_url_for_recording(recording_mbid: str) -> str | None:
    mbid = (recording_mbid or "").strip()
    if not mbid:
        return None

    url = f"https://musicbrainz.org/ws/2/recording/{mbid}"
    headers = {"User-Agent": _musicbrainz_user_agent(), "Accept": "application/json"}
    try:
        _mb_throttle()
        resp = requests.get(
            url, params={"fmt": "json", "inc": "releases"}, headers=headers, timeout=12
        )
    except requests.RequestException:
        return None
    if resp.status_code != 200:
        return None
    try:
        data = resp.json()
    except ValueError:
        return None

    releases = data.get("releases") or []
    if not releases:
        return None

    def _release_group_id_for_release(release_id: str) -> str | None:
        rid = (release_id or "").strip()
        if not rid:
            return None
        url = f"https://musicbrainz.org/ws/2/release/{rid}"
        headers = {
            "User-Agent": _musicbrainz_user_agent(),
            "Accept": "application/json",
        }
        try:
            _mb_throttle()
            resp = requests.get(
                url,
                params={"fmt": "json", "inc": "release-groups"},
                headers=headers,
                timeout=12,
            )
        except requests.RequestException:
            return None
        if resp.status_code != 200:
            return None
        try:
            data = resp.json()
        except ValueError:
            return None
        rg = data.get("release-group") or {}
        rgid = (rg.get("id") or "").strip()
        return rgid or None

    for rel in releases[:5]:
        release_id = (rel.get("id") or "").strip()
        if not release_id:
            continue
        cover = _cover_art_url_for_release(release_id)
        if cover:
            return cover
        rgid = _release_group_id_for_release(release_id)
        if rgid:
            cover = _cover_art_url_for_release_group(rgid)
            if cover:
                return cover

    return None


def _wikidata_qid_from_artist(mbid: str) -> str | None:
    mbid = (mbid or "").strip()
    if not mbid:
        return None
    url = f"https://musicbrainz.org/ws/2/artist/{mbid}"
    headers = {"User-Agent": _musicbrainz_user_agent(), "Accept": "application/json"}
    try:
        _mb_throttle()
        resp = requests.get(
            url, params={"fmt": "json", "inc": "url-rels"}, headers=headers, timeout=12
        )
    except requests.RequestException:
        return None
    if resp.status_code != 200:
        return None
    try:
        data = resp.json()
    except ValueError:
        return None

    rels = data.get("relations") or []
    for rel in rels:
        u = (rel.get("url") or {}).get("resource") or ""
        u = u.strip()
        if "wikidata.org/wiki/" in u:
            qid = u.rsplit("/", 1)[-1].strip()
            if qid.startswith("Q"):
                return qid
    return None


def _artist_image_url(artist_mbid: str) -> str | None:
    qid = _wikidata_qid_from_artist(artist_mbid)
    if not qid:
        return None

    url = f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
    headers = {"Accept": "application/json", "User-Agent": _musicbrainz_user_agent()}
    try:
        _wikidata_throttle()
        resp = requests.get(url, headers=headers, timeout=10)
    except requests.RequestException:
        return None
    if resp.status_code != 200:
        return None
    try:
        data = resp.json()
    except ValueError:
        return None

    entity = (data.get("entities") or {}).get(qid) or {}
    claims = entity.get("claims") or {}
    p18 = claims.get("P18") or []
    if not p18:
        return None
    mainsnak = p18[0].get("mainsnak") or {}
    datavalue = mainsnak.get("datavalue") or {}
    filename = datavalue.get("value") or ""
    filename = str(filename).strip()
    if not filename:
        return None

    try:
        width = int((os.environ.get("ART_IMAGE_WIDTH") or "1000").strip())
    except ValueError:
        width = 1000
    width = max(200, min(2000, width))

    safe = quote(filename.replace(" ", "_"), safe="")
    return f"https://commons.wikimedia.org/wiki/Special:FilePath/{safe}?width={width}"


def _cached_artist_image_url(
    *, artist_name: str, artist_mbid: str | None
) -> str | None:
    primary = strip_artist_features(artist_name)
    if not primary:
        return None

    mbid = (artist_mbid or "").strip() or None
    key_by_mbid = f"artist_mbid:{mbid}" if mbid else None
    key_by_name = f"artist_name:{primary.lower()}"

    if key_by_mbid:
        cached = get_cached_subject_image(key_by_mbid, max_age_days=45)
        if cached:
            return cached
    cached = get_cached_subject_image(key_by_name, max_age_days=45)
    if cached:
        return cached

    mbid_to_use = mbid
    if not mbid_to_use:
        try:
            items, _ = _mb_search("artist", primary, limit=5, offset=0)
        except Exception:
            items = []

        def _norm(s: str) -> str:
            return " ".join((s or "").strip().lower().split())

        want = _norm(primary)
        best = None
        for it in items or []:
            title = it.get("title") or ""
            if _norm(title) == want:
                best = it
                break
        if not best and items:
            best = max(items, key=lambda it: int(it.get("score") or 0))
        mbid_to_use = (best or {}).get("mbid") or None

    if not mbid_to_use:
        return None

    url = _artist_image_url(mbid_to_use)
    if not url:
        return None

    # Cache under both keys for better hit rate.
    set_cached_subject_image(key_by_name, url)
    set_cached_subject_image(f"artist_mbid:{mbid_to_use}", url)
    if key_by_mbid:
        set_cached_subject_image(key_by_mbid, url)
    return url


def _artist_credit_to_string(credit) -> str:
    if not credit:
        return ""
    parts = []
    for c in credit:
        name = (c.get("name") or "").strip()
        joinphrase = c.get("joinphrase") or ""
        if name:
            parts.append(name + joinphrase)
    return "".join(parts).strip()


def _year_from_date(date_str: str | None) -> str:
    s = (date_str or "").strip()
    return s[:4] if len(s) >= 4 else ""


def _mb_escape_phrase(v: str) -> str:
    return (v or "").replace('"', '\\"').strip()


def _mb_query_tokens(v: str) -> list[str]:
    raw = (v or "").strip().lower()
    raw = re.sub(r"[\'`’]", "", raw)
    normalized = re.sub(r"[^\w]+", " ", raw)
    seen: set[str] = set()
    out: list[str] = []
    for token in normalized.split():
        t = token.strip("_")
        if not t or t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out[:8]


def _mb_field_expr(field: str, text: str) -> str:
    tokens = _mb_query_tokens(text)
    if not tokens:
        return ""
    return "(" + " AND ".join([f"{field}:{t}*" for t in tokens]) + ")"


def _mb_search(
    kind: str, q: str, *, limit: int, offset: int, artist: str | None = None
):
    kind = (kind or "").strip().lower()
    q = (q or "").strip()
    if not q:
        return [], 0
    artist = (artist or "").strip()

    endpoint = "artist"
    key = "artists"
    kind_label = "Artist"
    if kind == "album":
        endpoint = "release-group"
        key = "release-groups"
        kind_label = "Album"
    elif kind == "song":
        endpoint = "recording"
        key = "recordings"
        kind_label = "Song"

    url = f"https://musicbrainz.org/ws/2/{endpoint}"

    title_field = "name"
    if kind == "song":
        title_field = "recording"
    elif kind == "album":
        title_field = "releasegroup"

    title_expr = _mb_field_expr(title_field, q)
    artist_expr = _mb_field_expr("artist", artist) if artist else ""
    queries: list[str] = []

    if title_expr and artist_expr and kind in {"song", "album"}:
        queries.append(f"{title_expr} AND {artist_expr}")
    elif title_expr:
        queries.append(title_expr)

    if artist and kind in {"song", "album"}:
        queries.append(f"{q} {artist}".strip())
    queries.append(q)

    seen_q: set[str] = set()
    normalized_queries: list[str] = []
    for qq in queries:
        key_q = (qq or "").strip()
        if not key_q or key_q in seen_q:
            continue
        seen_q.add(key_q)
        normalized_queries.append(key_q)

    headers = {"User-Agent": _musicbrainz_user_agent(), "Accept": "application/json"}

    data = {}
    raw_items = []
    total_count = 0
    for query in normalized_queries:
        params = {
            "query": query,
            "fmt": "json",
            "limit": int(limit),
            "offset": int(offset),
        }
        _mb_throttle()
        resp = requests.get(url, params=params, headers=headers, timeout=12)
        if resp.status_code >= 400:
            continue
        data = resp.json()
        raw_items = data.get(key) or []
        total_count = int(data.get("count") or 0)
        if raw_items:
            break

    if not raw_items and not data:
        return [], 0

    raw_items = data.get(key) or []
    total_count = int(data.get("count") or 0)

    out = []
    for item in raw_items:
        mbid = item.get("id") or ""
        features = ""
        if kind == "artist":
            title = item.get("name") or ""
            artist = ""
            year = _year_from_date(item.get("life-span", {}).get("begin"))
            dis = item.get("disambiguation") or ""
        elif kind == "album":
            title = item.get("title") or ""
            artist = _artist_credit_to_string(item.get("artist-credit"))
            year = _year_from_date(item.get("first-release-date"))
            primary = (item.get("primary-type") or "").strip()
            dis = primary
            secondary = item.get("secondary-types") or []
            sec_clean = [str(s).strip() for s in secondary if str(s).strip()]
            features = ", ".join(sec_clean)
        else:  # song
            title = item.get("title") or ""
            credits = item.get("artist-credit") or []
            artist = _artist_credit_to_string(credits)
            year = _year_from_date(item.get("first-release-date"))
            dis = ""
            credit_names: list[str] = []
            for c in credits:
                if isinstance(c, dict):
                    n = ((c.get("artist") or {}).get("name") or "").strip()
                    if n:
                        credit_names.append(n)
            if len(credit_names) > 1:
                features = ", ".join(credit_names[1:])

        score = item.get("score")
        try:
            score = int(score) if score is not None else None
        except (TypeError, ValueError):
            score = None

        entity_path = endpoint
        if endpoint == "release-group":
            entity_path = "release-group"
        url_out = f"https://musicbrainz.org/{entity_path}/{mbid}" if mbid else None

        out.append(
            {
                "title": title,
                "artist": artist,
                "year": year,
                "disambiguation": dis,
                "score": score,
                "features": features,
                "url": url_out,
                "mbid": mbid,
                "kind_label": kind_label,
            }
        )

    def _norm(s: str) -> str:
        return " ".join((s or "").strip().lower().split())

    deduped = []
    seen: set[tuple[str, str]] = set()
    for it in out:
        key = (_norm(it.get("title") or ""), _norm(it.get("artist") or ""))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(it)

    return deduped, total_count


@app.route("/api/musicbrainz/search", methods=["GET"])
def musicbrainz_search_api():
    q = (request.args.get("q") or "").strip()
    raw_kind = (request.args.get("kind") or "artist").strip().lower()
    kind = raw_kind if raw_kind in {"artist", "album", "song"} else "artist"
    artist = (request.args.get("artist") or "").strip()
    try:
        limit = int((request.args.get("limit") or "8").strip())
    except ValueError:
        limit = 8
    limit = max(1, min(20, limit))

    try:
        items, count = _mb_search(kind, q, limit=limit, offset=0, artist=artist)
        return jsonify({"ok": True, "kind": kind, "count": count, "items": items})
    except requests.RequestException:
        return jsonify({"ok": False, "error": "Something went wrong. Try again."}), 502
    except ValueError:
        return jsonify({"ok": False, "error": "Something went wrong. Try again."}), 502


# Home page
@app.route("/")
def home():
    raw_order = (request.args.get("order") or "recent").strip().lower()
    active_order = raw_order if raw_order in {"recent", "oldest"} else "recent"

    page, per_page, offset = _parse_pagination()
    raw_ratings = get_ratings(limit=per_page + 1, offset=offset, order=active_order)
    has_next = len(raw_ratings) > per_page
    ratings = raw_ratings[:per_page]
    owner_pics = _get_owner_pics_for_ratings(ratings)
    reactions_map = _build_subject_rating_emojis_map(ratings)
    percent_map = _build_percent_map(ratings)

    return render_template(
        "index.html",
        ratings=ratings,
        active_order=active_order,
        owner_pics=owner_pics,
        reactions_map=reactions_map,
        percent_map=percent_map,
        pagination=_pagination_context(
            page=page,
            per_page=per_page,
            has_next=has_next,
            item_count=len(ratings),
        ),
    )


###############################################
# Helper Functions
###############################################

# Source for emojis: https://getemoji.com/
REACTION_EMOJIS = [
    "👍",
    "👌",
    "🙌",
    "🤝",
    "💯",
    "❤️",
    "🖤",
    "💔",
    "💙",
    "💜",
    "💚",
    "🤍",
    "🧡",
    "💛",
    "😂",
    "🤣",
    "😭",
    "🥲",
    "😅",
    "😮",
    "🤯",
    "😳",
    "😱",
    "😢",
    "😤",
    "😮‍💨",
    "😡",
    "🤬",
    "🔥",
    "🥵",
    "🥶",
    "⚡",
    "💥",
    "👏",
    "🎶",
    "🎵",
    "🎧",
    "🔊",
    "🔁",
    "🎉",
    "✨",
    "🌟",
    "💫",
    "🤔",
    "🧠",
    "🧐",
    "🤨",
    "👎",
    "👀",
    "🙏",
    "🫡",
    "⭐",
    "🏆",
    "🥇",
    "📌",
    "📝",
    "🗑️",
]


def _build_reactions_map(ratings):
    reactions_map = {}
    if not ratings:
        return reactions_map

    rating_keys: list[int] = []
    for rating in ratings:
        try:
            rating_keys.append(int(rating[0]))
        except (TypeError, ValueError, IndexError):
            continue

    counts_map = get_reaction_counts_for_ratings(rating_keys)

    for rk in rating_keys:
        counts = counts_map.get(int(rk), []) or []
        if not counts:
            reactions_map[int(rk)] = []
            continue

        groups: dict[int, list[str]] = {}
        for emoji, c in counts:
            try:
                cnt = int(c)
            except (TypeError, ValueError):
                cnt = 0
            groups.setdefault(cnt, []).append(str(emoji))

        picked: list[str] = []
        for cnt in sorted(groups.keys(), reverse=True):
            bucket = groups.get(cnt) or []
            random.shuffle(bucket)
            for em in bucket:
                if not em:
                    continue
                picked.append(em)
                if len(picked) >= 5:
                    break
            if len(picked) >= 5:
                break

        reactions_map[int(rk)] = picked
    return reactions_map


def _build_subject_rating_emojis_map(ratings):
    out: dict[int, list[str]] = {}
    if not ratings:
        return out

    rating_keys: list[int] = []
    for rating in ratings:
        try:
            rating_keys.append(int(rating[0]))
        except (TypeError, ValueError, IndexError):
            continue

    counts_map = get_subject_rating_emoji_counts_for_rating_keys(rating_keys)
    for rk in rating_keys:
        counts = counts_map.get(int(rk), []) or []
        counts_sorted = sorted(
            counts,
            key=lambda t: (-int(t[1] or 0), str(t[0] or "")),
        )
        picked: list[str] = []
        for emoji, _cnt in counts_sorted:
            em = str(emoji or "").strip()
            if not em:
                continue
            picked.append(em)
            if len(picked) >= 3:
                break
        out[int(rk)] = picked
    return out


def _build_percent_map(ratings):
    percent_map = {}
    if not ratings:
        return percent_map

    def _to_score(v):
        try:
            n = int(v)
        except (TypeError, ValueError):
            return None
        return n if 1 <= n <= 10 else None

    def _overall_percent_from_rating_tuple(rating) -> int | None:
        if not rating:
            return None

        cand1: list[int] = []
        if len(rating) >= 8:
            for idx in (3, 4, 5, 6, 7):
                s = _to_score(rating[idx])
                if s is not None:
                    cand1.append(s)

        cand2: list[int] = []
        if len(rating) >= 12:
            for idx in (3, 5, 7, 9, 11):
                s = _to_score(rating[idx])
                if s is not None:
                    cand2.append(s)

        scores = cand2 if len(cand2) > len(cand1) else cand1
        if not scores:
            return None
        avg = sum(scores) / len(scores)
        return int(round(avg * 10))

    for rating in ratings:
        try:
            rk = int(rating[0])
        except (TypeError, ValueError, IndexError):
            continue
        percent_map[rk] = _overall_percent_from_rating_tuple(rating)

    return percent_map


ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}


def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


#  checks if an image file exists
def _pic_exists(rel_path: str) -> bool:
    if not rel_path:
        return False
    rel_path = rel_path.strip()

    upload_url_prefix = (
        current_app.config.get("UPLOAD_URL_PREFIX") or "/uploads"
    ).rstrip("/")
    if upload_url_prefix and rel_path.startswith(upload_url_prefix + "/"):
        fs_path = (
            Path(current_app.config.get("UPLOAD_FOLDER"))
            / rel_path[len(upload_url_prefix) + 1 :]
        )

    elif rel_path.startswith("/static/uploads/"):
        fs_path = (
            Path(current_app.config.get("UPLOAD_FOLDER"))
            / rel_path[len("/static/uploads/") :]
        )
    elif rel_path.startswith("/static/"):
        fs_path = Path(current_app.static_folder) / rel_path[len("/static/") :]
    else:
        fs_path = Path(current_app.root_path) / rel_path.lstrip("/")
    return fs_path.exists()


def _get_owner_pics_for_ratings(ratings):
    if not ratings:
        return {}

    owner_usernames = {
        (rating[8] or "").strip()
        for rating in ratings
        if len(rating) > 8 and (rating[8] or "").strip()
    }

    raw_owner_pics = get_profile_pics_by_usernames(owner_usernames)

    owner_pics = {}
    for username in owner_usernames:
        picture_path = raw_owner_pics.get(username)
        if not _pic_exists(picture_path):
            picture_path = None
        owner_pics[username] = picture_path
    return owner_pics


def _redirect_back(default_path, fragment=None):
    ref = request.referrer
    if ref and ref.startswith(request.host_url):
        if fragment:
            parts = urlsplit(ref)
            ref = urlunsplit(
                (parts.scheme, parts.netloc, parts.path, parts.query, fragment)
            )
        return redirect(ref)
    if fragment and "#" not in default_path:
        return redirect(f"{default_path}#{fragment}")
    return redirect(default_path)


def _safe_internal_url(candidate: str, fallback: str = "/") -> str:
    if not candidate:
        return fallback
    candidate = candidate.strip()
    if candidate.startswith("/"):
        return candidate
    try:
        parts = urlsplit(candidate)
    except ValueError:
        return fallback

    if parts.scheme and parts.netloc:
        host_parts = urlsplit(request.host_url)
        if parts.netloc != host_parts.netloc:
            return fallback

    if not parts.path.startswith("/"):
        return fallback
    return urlunsplit(("", "", parts.path, parts.query, parts.fragment))


def _format_time_ago(iso_timestamp: str) -> str:
    if not iso_timestamp:
        return "just now"
    try:
        parsed = datetime.fromisoformat(iso_timestamp)
    except ValueError:
        return "just now"
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    delta = now - parsed
    seconds = max(0, int(delta.total_seconds()))
    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} min"
    hours = minutes // 60
    if hours < 24:
        unit = "hr" if hours == 1 else "hrs"
        return f"{hours} {unit}"
    days = hours // 24
    if days < 7:
        unit = "day" if days == 1 else "days"
        return f"{days} {unit}"
    weeks = days // 7
    if weeks < 5:
        unit = "wk" if weeks == 1 else "wks"
        return f"{weeks} {unit}"
    months = days // 30
    if months < 12:
        unit = "mo" if months == 1 else "mos"
        return f"{months} {unit}"
    years = days // 365
    unit = "yr" if years == 1 else "yrs"
    return f"{years} {unit}"


def _parse_pagination(
    *,
    default_per_page: int = 5,
    allowed_per_page: tuple[int, ...] = (5, 10, 20, 30, 50, 100),
) -> tuple[int, int, int]:

    raw_page = (request.args.get("page") or "1").strip()
    raw_per_page_arg = request.args.get("per_page")
    raw_per_page = (raw_per_page_arg or "").strip()

    try:
        page = int(raw_page)
    except ValueError:
        page = 1
    page = max(1, page)

    try:
        per_page = int(raw_per_page)
    except ValueError:
        per_page = None

    if per_page is None:
        saved = session.get("pagination_per_page")
        try:
            saved_per_page = int(saved) if saved is not None else None
        except (TypeError, ValueError):
            saved_per_page = None

        if saved_per_page in allowed_per_page:
            per_page = saved_per_page
        else:
            per_page = default_per_page

    if per_page not in allowed_per_page:
        per_page = default_per_page

    if raw_per_page_arg is not None and per_page in allowed_per_page:
        session["pagination_per_page"] = per_page

    offset = (page - 1) * per_page
    return page, per_page, offset


def _pagination_context(
    *,
    page: int,
    per_page: int,
    has_next: bool,
    item_count: int,
    min_items_to_show: int = 5,
    options: list[int] | None = None,
):
    args = request.args.to_dict(flat=True)

    if options is None:
        options = [5, 10, 20, 30, 50, 100]

    def _url_for_page(target_page: int) -> str:
        next_args = dict(args)
        next_args["page"] = str(target_page)
        next_args["per_page"] = str(per_page)
        qs = urlencode(next_args)
        return f"{request.path}?{qs}" if qs else request.path

    other_args = [(k, v) for k, v in args.items() if k not in {"page", "per_page"}]
    prev_url = _url_for_page(page - 1) if page > 1 else None
    next_url = _url_for_page(page + 1) if has_next else None

    show = bool(prev_url or next_url or (item_count > min_items_to_show))

    return {
        "page": page,
        "per_page": per_page,
        "options": options,
        "other_args": other_args,
        "prev_url": prev_url,
        "next_url": next_url,
        "show": show,
    }
