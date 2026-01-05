from flask import Blueprint, render_template, request, redirect, flash, current_app
from werkzeug.utils import secure_filename
from pathlib import Path
from flask_login import login_user, logout_user, login_required, current_user
from backend.database import (
    get_ratings,
    get_rating_by_key,
    add_rating,
    update_rating,
    delete_rating,
    create_user,
    get_user_by_username_or_email,
    verify_password,
    get_rating_owner,
    update_profile_pic,
    get_profile_pic_by_username,
)

app = Blueprint("main", __name__)

# Home page
@app.route("/")
def home(): # Get all ratings from the database
    ratings = get_ratings()

    # Extract the usernames of all owners who have ratings
    owner_usernames = {rating[8] for rating in ratings} if ratings else set()

    # Build a dictionary of {username: profile_picture_path or None}
    owner_pics = {}
    for username in owner_usernames:
        picture_path = get_profile_pic_by_username(username)

        # If the picture doesn't exist in file path, set to None
        if not _pic_exists(picture_path):
            picture_path = None

        owner_pics[username] = picture_path

    # Render the page with all ratings and their associated profile pictures
    return render_template("index.html", ratings=ratings, owner_pics=owner_pics)


# Authentication page
@app.route("/auth")
def auth():
    if current_user.is_authenticated:
        return redirect("/browse")
    login = request.args.get("login") == "true"
    error = request.args.get("error")
    next_url = request.args.get("next")
    return render_template("auth.html", login=login, error=error, next=next_url)


# Signup user
@app.route("/signup", methods=["POST"])
def signup():
    username = request.form.get("username", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")
    confirm = request.form.get("confirm_password", "")
    next_url = request.form.get("next")
    if not username or not email or not password or password != confirm:
        flash("Please complete all fields and ensure passwords match.", "error")
        return redirect("/auth" + ("?next=" + next_url if next_url else ""))
    user = create_user(username, email, password)
    if not user:  # username or email taken
        flash("That username or email is already taken.", "error")
        return redirect("/auth")
    login_user(user)
    if next_url and next_url.startswith("/"):
        return redirect(next_url)
    return redirect("/browse")


# Login user
@app.route("/login", methods=["POST"])
def login():
    identifier = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    next_url = request.form.get("next")
    user = get_user_by_username_or_email(identifier)
    if not user or not verify_password(user.password_hash, password):
        flash("Invalid username/email or password.", "error")
        return redirect("/auth?login=true" + ("&next=" + next_url if next_url else ""))
    login_user(user)
    if next_url and next_url.startswith("/"):
        return redirect(next_url)
    return redirect("/profile")


# Logout user
@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect("/")


# Browse page (list all ratings)
@app.route("/browse")
def browse():
    # Get all ratings from the database
    ratings = get_ratings()

    # Extract the usernames of all owners who have ratings
    owner_usernames = {rating[8] for rating in ratings} if ratings else set()

    # Build a dictionary of {username: profile_picture_path or None}
    owner_pics = {}
    for username in owner_usernames:
        picture_path = get_profile_pic_by_username(username)

        # If the picture doesn't exist in file path, set to None
        if not _pic_exists(picture_path):
            picture_path = None

        owner_pics[username] = picture_path

    # Render the page with all ratings and their associated profile pictures
    return render_template("browse.html", ratings=ratings, owner_pics=owner_pics)


# View rating details
@app.route("/rating/<int:rating_key>")
def rating_detail(rating_key):
    rating = get_rating_by_key(rating_key)
    if not rating:
        return redirect("/browse")
    owner = get_rating_owner(rating_key)

    owner_pic = get_profile_pic_by_username(owner) if owner else None
    if owner_pic and not _pic_exists(owner_pic):
        owner_pic = None
    return render_template(
        "rating.html", rating=rating, owner=owner, owner_pic=owner_pic
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
    return render_template("add.html")


# Profile page
@app.route("/profile", methods=["GET"])
@login_required
def profile():
    # If the saved picture path doesn't point to a real file anymore,
    # this temporarily set it to None so the template shows the default image.
    if current_user.profile_pic and not _pic_exists(current_user.profile_pic):
        current_user.profile_pic = None
    return render_template("profile.html")


# Upload new profile picture (setup code)
@app.route("/profile/upload", methods=["POST"])
@login_required
def upload_profile_pic():
    file = request.files.get("profile_pic")
    if not file or file.filename == "":
        flash("No file selected.", "error")
        return redirect("/profile")
    if not _allowed_file(file.filename):
        flash("Unsupported file type.", "error")
        return redirect("/profile")

    upload_folder = Path(current_app.config.get("UPLOAD_FOLDER"))
    upload_folder.mkdir(parents=True, exist_ok=True)

    ext = file.filename.rsplit(".", 1)[1].lower()
    filename = secure_filename(f"user_{current_user.id}.{ext}")
    save_path = upload_folder / filename
    file.save(str(save_path))

    rel_path = f"/static/uploads/{filename}"
    update_profile_pic(current_user.id, rel_path)
    flash("Profile picture updated.", "profile")
    return redirect("/profile")


# Remove the user's profile picture
@app.route("/profile/remove", methods=["POST"])
@login_required
def remove_profile_pic():
    update_profile_pic(current_user.id, None)
    flash("Profile picture removed.", "profile")
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
    return render_template("edit.html", rating=rating)


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


################################
# Helper Functions
################################

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}


def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


#  checks if an image file exists (setup code)
def _pic_exists(rel_path: str) -> bool:
    if not rel_path:
        return False
    fs_path = Path(current_app.root_path) / rel_path.lstrip("/")
    return fs_path.exists()
