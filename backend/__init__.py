from flask import Flask, request, session, redirect, flash
from flask_login import LoginManager, current_user
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit

ROOT_DIR = Path(__file__).resolve().parent
BASE_DIR = ROOT_DIR.parent


# Set up code for Flask
def create_app():
    app = Flask(
        __name__,
        template_folder=str(BASE_DIR / "templates"),
        static_folder=str(BASE_DIR / "static"),
    )

    app.config["SECRET_KEY"] = "dev-secret-key"
    app.config["UPLOAD_FOLDER"] = str(BASE_DIR / "static" / "uploads")

    # Initialize database
    from backend._db_setup import init_db

    init_db()

    # Register routes with blueprint
    from backend.routes import app as routes_bp

    app.register_blueprint(routes_bp)

    # User model import
    from backend.database import (
        get_user_by_id,
        get_alerts_for_user,
        get_unread_alert_count,
        get_bulletin_feed_for_user,
        count_bulletin_feed_for_user,
        get_activity_feed_for_user,
        count_activity_feed_for_user,
    )

    # Flask-Login setup
    login_manager = LoginManager()
    login_manager.init_app(app)

    @login_manager.unauthorized_handler
    def _unauthorized():
        session["auth_mode"] = "login"
        # If this was a POST (like/submit/etc), don't save the POST-only endpoint
        # as next_url, because after login we'll redirect via GET and it will 404/405.
        next_url = None
        ref = request.referrer
        if request.method != "GET":
            if ref and ref.startswith(request.host_url):
                try:
                    parts = urlsplit(ref)
                    if not parts.scheme and not parts.netloc and parts.path.startswith("/"):
                        next_url = urlunsplit(("", "", parts.path, parts.query, ""))
                    elif parts.path.startswith("/"):
                        next_url = urlunsplit(("", "", parts.path, parts.query, ""))
                except Exception:
                    next_url = None
        if not next_url:
            # Preserve query string for GET requests
            full = (request.full_path or "").rstrip("?")
            next_url = full if full.startswith("/") else request.path
        session["next_url"] = next_url

        flash("You must be logged in first.", "error")

        if ref and ref.startswith(request.host_url):
            return redirect(ref)
        return redirect("/")

    @app.context_processor
    def inject_auth_sidebar_state():
        return {
            "login": session.get("auth_mode") == "signup",
            "next": session.get("next_url"),
        }

    @app.context_processor
    def inject_alerts_sidebar_state():
        if not current_user.is_authenticated:
            return {"alerts": [], "unread_alert_count": 0}

        alerts = get_alerts_for_user(current_user.id, limit=5, include_read=True)

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

        for a in alerts:
            a["time_ago"] = _format_time_ago(a.get("created_at") or "")
        unread_alert_count = get_unread_alert_count(current_user.id)
        return {"alerts": alerts, "unread_alert_count": unread_alert_count}

    @app.context_processor
    def inject_bulletin_sidebar_state():
        if not current_user.is_authenticated:
            return {"bulletins": [], "bulletin_count": 0}

        items = get_bulletin_feed_for_user(current_user.id, limit=5)
        bulletin_count = count_bulletin_feed_for_user(current_user.id)

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

        for p in items:
            p["time_ago"] = _format_time_ago(p.get("created_at") or "")

        return {"bulletins": items, "bulletin_count": bulletin_count}

    @app.context_processor
    def inject_activity_sidebar_state():
        if not current_user.is_authenticated:
            return {"activities": [], "activity_count": 0}

        raw_items = get_activity_feed_for_user(current_user.id, limit=5)
        activity_count = count_activity_feed_for_user(current_user.id)

        def _format(item: dict) -> dict:
            actor = item.get("actor_username") or ""
            action = item.get("action") or ""
            entity_label = item.get("entity_label") or ""
            url = item.get("url") or ""
            metadata = item.get("metadata") or {}

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

            return {"text": text, "url": url, "action": action}

        return {
            "activities": [_format(i) for i in raw_items],
            "activity_count": activity_count,
        }

    @login_manager.user_loader
    def load_user(user_id):
        return get_user_by_id(int(user_id))

    return app
