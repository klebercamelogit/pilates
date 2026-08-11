from flask import Flask

from app.config import Config
from app import db as db_module


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db_module.init_app(app)

    from app.auth.routes import bp as auth_bp
    from app.scheduling.routes import bp as scheduling_bp
    from app.admin.routes import bp as admin_bp
    from app.records.routes import bp as records_bp
    from app.records.prontuario_routes import bp as prontuario_bp
    from app.views import bp as views_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(scheduling_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(records_bp)
    app.register_blueprint(prontuario_bp)
    app.register_blueprint(views_bp)

    @app.route("/api/health")
    def health():
        return {"status": "ok"}

    return app
