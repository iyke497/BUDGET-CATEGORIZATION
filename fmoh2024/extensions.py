# fmoh2024/extensions.py
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_caching import Cache
from sqlalchemy import event

# Initialize extensions here, without binding to app yet
db = SQLAlchemy()
migrate = Migrate()

cache = Cache(config={
    'CACHE_TYPE': 'SimpleCache',  # Simple in-memory cache
    'CACHE_DEFAULT_TIMEOUT': 300,  # 5 minutes
    'CACHE_THRESHOLD': 100  # Max number of items
})

def enable_wal_mode():
    """Enable WAL mode for SQLite for better concurrency"""
    @event.listens_for(db.engine, 'connect')
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        # Enable WAL mode for better concurrency
        cursor.execute("PRAGMA journal_mode=WAL")
        # Increase timeout for busy operations
        cursor.execute("PRAGMA busy_timeout=5000")  # 5 seconds
        # Enable foreign keys
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()