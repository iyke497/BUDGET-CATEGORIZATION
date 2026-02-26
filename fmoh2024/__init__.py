import os

from flask import Flask

from fmoh2024.commands import register_commands
from fmoh2024.compliance import bp as compliance_bp
from fmoh2024.projects import bp as projects_bp
from fmoh2024.config import config
from fmoh2024.extensions import db, migrate
from fmoh2024.logging import init_logging
from fmoh2024.main import bp as main_bp


def create_app(config_name=None):
    init_logging()  # should be configured before any access to app.logger

    if config_name is None:
        config_name = os.getenv("FLASK_ENV", "default")

    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Initialize extensions with the app
    db.init_app(app)
    migrate.init_app(app, db)

    # Register CLI commands
    register_commands(app)

    # Register blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(compliance_bp)
    app.register_blueprint(projects_bp)

    return app
