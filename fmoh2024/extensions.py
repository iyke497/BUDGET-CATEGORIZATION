# fmoh2024/extensions.py
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

# Initialize extensions here, without binding to app yet
db = SQLAlchemy()
migrate = Migrate()
