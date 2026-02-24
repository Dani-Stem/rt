from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    flash,
    current_app,
    session,
)
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit
from urllib.parse import urlencode
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
    get_rating_comments,
    add_rating_comment,
    get_rating_comment,
    update_rating_comment,
    delete_rating_comment,
)

# Initialize routes with Blueprint
# Blueprint is what allows the routes to work (@app.route etc.)
app = Blueprint("main", __name__)


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
    reactions_map = _build_reactions_map(ratings)
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
    reactions_map = _build_reactions_map(ratings)
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

    # Only allow internal redirects
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


@app.route("/charts")
def charts():
    return render_template("charts.html")


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
    return redirect(_safe_internal_url(next_url, fallback="/activity"))


@app.route("/activity/clear", methods=["POST"])
@login_required
def activity_clear():
    next_url = (request.form.get("next") or "").strip()
    raw_tab = (request.form.get("tab") or "all").strip().lower()
    allowed_tabs = {"all", "users", "artists", "albums", "songs", "genres"}
    tab = raw_tab if raw_tab in allowed_tabs else "all"
    clear_activity_for_user(current_user.id, tab)
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

    message = (request.form.get("message") or "").strip()
    post_type = (request.form.get("type") or "").strip().lower()
    title = (request.form.get("title") or "").strip().lower()

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

    if len(message) > 500:
        flash("Bulletin message is too long (max 500 characters).", "error")
        return redirect(request.referrer or "/")

    bulletin_key = add_bulletin_post(
        current_user.id,
        current_user.username,
        message,
        title,
        post_type=post_type,
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
        metadata={"message_length": len(message), "title": title, "type": post_type},
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

    percent = random.randint(70, 99)

    detail_reactions = {}
    for category in ("Lyrics", "Beat", "Flow", "Melody", "Cohesive"):
        detail_reactions[category] = random.sample(REACTION_EMOJIS, k=5)

    owner_pic = get_profile_pic_by_username(owner) if owner else None
    if owner_pic and not _pic_exists(owner_pic):
        owner_pic = None
    comments = _build_rating_comments(rating_key)

    return render_template(
        "rating.html",
        rating=rating,
        owner=owner,
        owner_pic=owner_pic,
        detail_reactions=detail_reactions,
        percent=percent,
        liked=liked,
        rating_image_url=rating_image_url,
        category_vote_summary=category_vote_summary,
        user_category_votes=user_category_votes,
        can_category_vote=current_user.is_authenticated,
        comments=comments,
    )


@app.route("/rating/<int:rating_key>/category-vote", methods=["POST"])
@login_required
def rating_category_vote(rating_key: int):
    rating = get_rating_by_key(rating_key)
    if not rating:
        return redirect(f"/rating/{rating_key}")

    category = (request.form.get("category") or "").strip()
    direction = (request.form.get("direction") or "").strip().lower()

    allowed = {"Lyrics", "Beat", "Flow", "Melody", "Cohesive"}
    if category not in allowed:
        flash("Invalid category.", "error")
        return _redirect_back(f"/rating/{rating_key}")

    vote = 0
    if direction == "up":
        vote = 1
    elif direction == "down":
        vote = -1
    else:
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

            rating_image_url = f"/static/uploads/ratings/{filename}"

        if rating_type:
            rating_key = add_rating(
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
                current_user.username,
                rating_image_url,
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
    return render_template("add.html", form_action="/add", draft=draft or {})


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
    profile_percent_map = {
        rating[0]: random.randint(60, 99) for rating in profile_ratings
    }
    favorite_ratings = get_liked_ratings_for_user(profile_user.id, limit=60)
    favorite_percent_map = {
        rating[0]: random.randint(60, 99) for rating in favorite_ratings
    }
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
    percent_map = {rating[0]: random.randint(60, 99) for rating in ratings}
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
    percent_map = {rating[0]: random.randint(60, 99) for rating in favorites}
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

    rel_path = f"/static/uploads/{filename}"
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
            rating_image_url = f"/static/uploads/ratings/{filename}"

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
# Helper Functions
###############################################

# Source for emojis: https://getemoji.com/
REACTION_EMOJIS = [
    "👍",
    "❤️",
    "😂",
    "😮",
    "😢",
    "😡",
    "🔥",
    "👏",
    "🎉",
    "🤔",
    "👎",
    "⭐",
]


def _build_reactions_map(ratings):
    reactions_map = {}
    if not ratings:
        return reactions_map

    current_username = current_user.username if current_user.is_authenticated else None
    for rating in ratings:
        rating_key = rating[0]
        owner_username = rating[8]
        if current_username and owner_username == current_username:
            continue
        reactions_map[rating_key] = random.sample(REACTION_EMOJIS, k=5)
    return reactions_map


def _build_percent_map(ratings):
    percent_map = {}
    if not ratings:
        return percent_map

    current_username = current_user.username if current_user.is_authenticated else None

    for rating in ratings:
        rating_key = rating[0]
        owner_username = rating[8]

        if current_username and owner_username == current_username:
            continue

        # Random percent
        percent_map[rating_key] = random.randint(60, 99)

    return percent_map


ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}


def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


#  checks if an image file exists
def _pic_exists(rel_path: str) -> bool:
    if not rel_path:
        return False
    if rel_path.startswith("/static/"):
        fs_path = Path(current_app.static_folder) / rel_path[len("/static/") :]
    else:
        fs_path = Path(current_app.root_path) / rel_path.lstrip("/")
    return fs_path.exists()


def _get_owner_pics_for_ratings(ratings):
    if not ratings:
        return {}

    owner_usernames = {rating[8] for rating in ratings}

    owner_pics = {}
    for username in owner_usernames:
        picture_path = get_profile_pic_by_username(username)
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
    default_per_page: int = 10,
    allowed_per_page: tuple[int, ...] = (10, 20, 30, 50, 100),
) -> tuple[int, int, int]:
    """Returns (page, per_page, offset)."""
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
    min_items_to_show: int = 10,
):
    args = request.args.to_dict(flat=True)

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
        "options": [10, 20, 30, 50, 100],
        "other_args": other_args,
        "prev_url": prev_url,
        "next_url": next_url,
        "show": show,
    }
