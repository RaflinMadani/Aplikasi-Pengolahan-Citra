from flask import Flask, jsonify, render_template

from config import Config
from .storage import SessionStore


def create_app(config_overrides=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if config_overrides:
        app.config.update(config_overrides)

    app.extensions["wm_store"] = SessionStore(app.config["STORAGE_DIR"], app.config["MAX_HISTORY"])

    from .api import bp
    app.register_blueprint(bp)

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.errorhandler(413)
    def too_large(_):
        return jsonify(error="Ukuran file melebihi batas 16 MB."), 413

    @app.errorhandler(404)
    def not_found(_):
        return jsonify(error="Sumber daya tidak ditemukan."), 404

    @app.errorhandler(Exception)
    def unhandled(e):
        from werkzeug.exceptions import HTTPException
        if isinstance(e, HTTPException):
            return jsonify(error=e.description), e.code
        app.logger.exception("Kesalahan tak terduga")
        return jsonify(error="Terjadi kesalahan pada server."), 500

    return app
