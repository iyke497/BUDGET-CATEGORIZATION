# fmoh2024/config.py
import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env file from the base directory
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)


class Config:
    BASE_DIR = Path(__file__).resolve().parent.parent

    # Flask settings
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-key-change-in-production")
    DEBUG = False
    TESTING = False

    # Database
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", f"sqlite:///{BASE_DIR}/budget.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # App specific
    APP_NAME = "Budget Categorization App"
    ITEMS_PER_PAGE = 20


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_ECHO = False  # Log SQL queries


class ProductionConfig(Config):
    SECRET_KEY = os.getenv("SECRET_KEY")
    # Use PostgreSQL in production if available
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}
