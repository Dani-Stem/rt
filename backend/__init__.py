from flask import Flask, request, session, redirect, flash
from flask_login import LoginManager
from pathlib import Path

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
    from backend.database import get_user_by_id

    # Flask-Login setup
    login_manager = LoginManager()
    login_manager.init_app(app)

    @login_manager.unauthorized_handler
    def _unauthorized():
        session["auth_mode"] = "login"
        session["next_url"] = request.path

        flash("You must be logged in to view that page.", "error")

        ref = request.referrer
        if ref and ref.startswith(request.host_url):
            return redirect(ref)
        return redirect("/")

    @app.context_processor
    def inject_auth_sidebar_state():
        return {
            "login": session.get("auth_mode") == "signup",
            "next": session.get("next_url"),
        }

    @login_manager.user_loader
    def load_user(user_id):
        return get_user_by_id(int(user_id))

    return app
