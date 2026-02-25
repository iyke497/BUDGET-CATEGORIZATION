# fmoh2024/compliance/__init__.py
from flask import Blueprint

bp = Blueprint("compliance", __name__, url_prefix="/compliance")

# Import routes at the bottom to avoid circular imports
from fmoh2024.compliance import routes
