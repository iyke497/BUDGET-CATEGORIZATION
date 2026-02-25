# fmoh2024/main/__init__.py
from flask import Blueprint

bp = Blueprint('main', __name__)

# Import routes at the bottom
from fmoh2024.main import routes