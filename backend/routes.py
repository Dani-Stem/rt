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
from werkzeug.utils import secure_filename
from pathlib import Path
from flask_login import login_user, logout_user, login_required, current_user
import random
from backend.database import (
    get_ratings,
    get_rating_by_key,
    add_rating,
    update_rating,
    delete_rating,
    create_user,
    get_users,
    get_user_by_id,
    get_user_by_username_or_email,
    verify_password,
    get_rating_owner,
    get_artist,
    update_profile_pic,
    update_profile_info,
    get_profile_pic_by_username,
    get_profile_comments as get_profile_comments_db,
    add_profile_comment as add_profile_comment_db,
    update_profile_comment as update_profile_comment_db,
    delete_profile_comment as delete_profile_comment_db,
)

# Initialize routes with Blueprint
# Blueprint is what allows the routes to work (@app.route etc.)
app = Blueprint("main", __name__)


# Home page
@app.route("/")
def home():
    ratings = get_ratings()
    owner_pics = _get_owner_pics_for_ratings(ratings)
    reactions_map = _build_reactions_map(ratings)
    percent_map = _build_percent_map(ratings)

    return render_template(
        "index.html",
        ratings=ratings,
        owner_pics=owner_pics,
        reactions_map=reactions_map,
        percent_map=percent_map,
    )


# Browse page (list all ratings)
@app.route("/browse")
def browse():
    ratings = get_ratings()

    owner_pics = _get_owner_pics_for_ratings(ratings)
    reactions_map = _build_reactions_map(ratings)
    percent_map = _build_percent_map(ratings)

    return render_template(
        "browse.html",
        ratings=ratings,
        owner_pics=owner_pics,
        reactions_map=reactions_map,
        percent_map=percent_map,
    )


@app.route("/favorites")
def favorites():
    ratings = get_ratings()

    owner_pics = _get_owner_pics_for_ratings(ratings)
    reactions_map = _build_reactions_map(ratings)
    percent_map = _build_percent_map(ratings)

    return render_template(
        "favorites.html",
        ratings=ratings,
        owner_pics=owner_pics,
        reactions_map=reactions_map,
        percent_map=percent_map,
    )


@app.route("/playlists")
def playlists():
    return render_template("playlists.html")


@app.route("/charts")
def charts():
    return render_template("charts.html")


@app.route("/genres")
def genres():
    return render_template("genres.html")


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

# View rating details
@app.route("/rating/<int:rating_key>")
def rating_detail(rating_key):
    rating = get_rating_by_key(rating_key)
    if not rating:
        return redirect("/browse")

    owner = get_rating_owner(rating_key)

    percent = random.randint(70, 99)

    detail_reactions = {}
    for category in ("Lyrics", "Beat", "Flow", "Melody", "Cohesive"):
        detail_reactions[category] = random.sample(REACTION_EMOJIS, k=5)

    owner_pic = get_profile_pic_by_username(owner) if owner else None
    if owner_pic and not _pic_exists(owner_pic):
        owner_pic = None

    return render_template(
        "rating.html",
        rating=rating,
        owner=owner,
        owner_pic=owner_pic,
        detail_reactions=detail_reactions,
        percent=percent,
    )


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
                current_user.username,
            )
        return redirect("/browse")
    return render_template("add.html", form_action="/add")


# Profile page
@app.route("/profile", methods=["GET"])
@login_required
def profile():
    if current_user.profile_pic and not _pic_exists(current_user.profile_pic):
        current_user.profile_pic = None
    stored_comments = get_profile_comments_db(current_user.id)
    display_comments = []
    for comment in stored_comments:
        profile_pic = comment.get("profile_pic")
        if profile_pic and not _pic_exists(profile_pic):
            profile_pic = None
        display_comments.append(
            {
                "comment_id": comment.get("comment_id"),
                "message": comment.get("message", ""),
                "username": comment.get("username", current_user.username),
                "profile_pic": profile_pic,
                "author_user_id": comment.get("author_user_id"),
                "time_ago": _format_time_ago(comment.get("created_at")),
            }
        )
    return render_template("profile.html", comments=display_comments)

@app.route("/artist-profile")
def artist_profile():
    return render_template("artist-profile.html")


@app.route("/artist-profile-expand")
def artist_profile_expand():
    return render_template("artist-profile-expand.html")

@app.route("/album-profile")
def album_profile():
    return render_template("album-profile.html")

@app.route("/album-profile-expand")
def album_profile_expand():
    return render_template("album-profile-expand.html")

@app.route("/song-profile")
def song_profile():
    return render_template("song-profile.html")

@app.route("/song-profile-expand")
def song_profile_expand():
    return render_template("song-profile-expand.html")

@app.route("/user-profile")
def user_profile():
    users = get_users()

    return render_template(
        "user-profile.html",
        users=users,
    )

@app.route("/user-profile-expand")
def user_profile_expand():
    return render_template("user-profile-expand.html")


# View profile details
@app.route("/profile/<int:user_info_key>")
def profile_detail(user_info_key):
    user_id = get_user_by_id(user_info_key)
    if not user_id:
        return redirect("/browse")

    return render_template(
        "profile.html",
        user_info_key=user_info_key,
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
        favorites0 = request.form.get("favorites0", "").strip()
        updated_username = username if username else current_user.username
        updated_about = about if about else current_user.about
        updated_favorites0 = favorites0 if favorites0 else current_user.favorites0
        if (
            updated_username != current_user.username
            or updated_about != current_user.about
            or updated_favorites0 != current_user.favorites0
        ):
            update_profile_info(current_user.id, updated_username, updated_about, updated_favorites0)
            current_user.username = updated_username
            current_user.about = updated_about
            current_user.favorites0 = updated_favorites0
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
    flash("Profile picture updated.", "profile")
    return redirect("/profile-edit")


# Remove the user's profile picture
@app.route("/profile/remove", methods=["POST"])
@login_required
def remove_profile_pic():
    update_profile_pic(current_user.id, None)
    flash("Profile picture removed.", "profile")
    return redirect("/profile-edit")


# Add profile comment
@app.route("/profile/comments", methods=["POST"])
@login_required
def add_profile_comment():
    message = request.form.get("comment", "").strip()
    if message:
        add_profile_comment_db(
            current_user.id,
            current_user.id,
            message,
            datetime.now(timezone.utc).isoformat(),
        )
    return redirect("/profile")


# Delete profile comment
@app.route("/profile/comments/delete/<int:comment_id>", methods=["POST"])
@login_required
def delete_profile_comment(comment_id):
    delete_profile_comment_db(comment_id, current_user.id)
    return redirect("/profile")


# Edit profile comment
@app.route("/profile/comments/edit/<int:comment_id>", methods=["POST"])
@login_required
def edit_profile_comment(comment_id):
    message = request.form.get("comment", "").strip()
    if message:
        update_profile_comment_db(comment_id, current_user.id, message)
    return redirect("/profile")


# Edit rating
@app.route("/edit/<int:rating_key>", methods=["GET", "POST"])
@login_required
def edit(rating_key):
    owner = get_rating_owner(rating_key)
    if not owner or owner != current_user.username:
        flash("You can only edit your own ratings.", "error")
        return redirect("/browse")
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
        return redirect("/browse")

    rating = get_rating_by_key(rating_key)
    if not rating:
        return redirect("/browse")
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
    delete_rating(rating_key)
    return redirect("/browse")


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

        # Don't show percent on the current user's own ratings
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
        fs_path = Path(current_app.static_folder) / rel_path.removeprefix("/static/")
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
        unit = "minute" if minutes == 1 else "minutes"
        return f"{minutes} {unit} ago"
    hours = minutes // 60
    if hours < 24:
        unit = "hour" if hours == 1 else "hours"
        return f"{hours} {unit} ago"
    days = hours // 24
    if days < 7:
        unit = "day" if days == 1 else "days"
        return f"{days} {unit} ago"
    weeks = days // 7
    if weeks < 5:
        unit = "week" if weeks == 1 else "weeks"
        return f"{weeks} {unit} ago"
    months = days // 30
    if months < 12:
        unit = "month" if months == 1 else "months"
        return f"{months} {unit} ago"
    years = days // 365
    unit = "year" if years == 1 else "years"
    return f"{years} {unit} ago"
