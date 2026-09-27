from flask import Flask, jsonify
from flask_cors import CORS

from auth import auth_bp
from config import Config
from db import close_db, init_db
from rate_limit import limiter
from routes import api_bp
from seed import seed_games


def create_app(overrides=None):
    app = Flask(__name__)
    Config.load(app)
    if overrides:
        app.config.update(overrides)

    if app.config.get("AUTO_INIT_DB", True):
        with app.app_context():
            init_db()
            seed_games()

    CORS(
        app,
        resources={r"/api/*": {"origins": app.config.get("ALLOWED_ORIGINS") or ["*"]}},
    )
    limiter.init_app(app)
    app.teardown_appcontext(close_db)

    app.register_blueprint(auth_bp)
    app.register_blueprint(api_bp)

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify(error="not_found"), 404

    return app
