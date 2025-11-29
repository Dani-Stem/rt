from flask import Flask
from flask_login import LoginManager
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
BASE_DIR = ROOT_DIR.parent


def create_app():
    app = Flask(
        __name__,
        template_folder=str(BASE_DIR / "templates"),
        static_folder=str(BASE_DIR / "static"),
    )

    app.config["SECRET_KEY"] = "dev-secret-key"
    app.config["UPLOAD_FOLDER"] = str(BASE_DIR / "static" / "uploads")

    # Initialize database schema
    from backend._db_setup import init_db

    init_db()

    # Register routes blueprint
    from backend.routes import app as routes_bp

    app.register_blueprint(routes_bp)

    # Login manager setup
    from backend.database import get_user_by_id

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "main.auth"

    @login_manager.user_loader
    def load_user(user_id):
        return get_user_by_id(int(user_id))

    return app
