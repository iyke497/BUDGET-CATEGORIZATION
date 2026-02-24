from flask import Flask
import os

from fmoh2024 import views
from fmoh2024.logging import init_logging
from fmoh2024.config import config


def create_app(config_name=None):
    init_logging()  # should be configured before any access to app.logger

    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'default')
    
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Optional: Still allow overrides for testing
    # app.config.from_prefixed_env()  # Remove if not needed
    
    app.register_blueprint(views.bp)
    
    return app