import os
from backend import create_app

app = create_app()

# Runs the app
if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))

    def _is_render() -> bool:
        return any(
            (os.environ.get(k) or "").strip()
            for k in (
                "RENDER",
                "RENDER_SERVICE_ID",
                "RENDER_EXTERNAL_URL",
                "RENDER_GIT_COMMIT",
            )
        )

    def _env_bool(key: str):
        raw = os.environ.get(key)
        if raw is None:
            return None
        return raw.strip().lower() in {"1", "true", "yes", "on"}

    debug = _env_bool("FLASK_DEBUG")
    if debug is None:
        debug = False if _is_render() else True

    app.run(host="0.0.0.0", port=port, debug=debug)
