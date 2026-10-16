import os

_db_path = os.environ.get("RECIPE_DB_PATH")
if not _db_path:
    raise RuntimeError("RECIPE_DB_PATH environment variable is required")


class Config:
    DATABASE = _db_path


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True


class ProductionConfig(Config):
    DEBUG = False