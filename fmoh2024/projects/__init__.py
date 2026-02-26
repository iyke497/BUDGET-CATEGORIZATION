from flask import Blueprint

bp = Blueprint("projects", __name__, url_prefix="/projects")

# Import routes to register them with the blueprint
from fmoh2024.projects import routes  # noqa: F401
