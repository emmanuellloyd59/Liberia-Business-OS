import os
class BaseConfig:
    SECRET_KEY=os.getenv("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI=os.getenv("DATABASE_URL","sqlite:///liberia_business_os.db")
    if SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URI=SQLALCHEMY_DATABASE_URI.replace("postgres://","postgresql+psycopg://",1)
    elif SQLALCHEMY_DATABASE_URI.startswith("postgresql://") and "+psycopg" not in SQLALCHEMY_DATABASE_URI:
        SQLALCHEMY_DATABASE_URI=SQLALCHEMY_DATABASE_URI.replace("postgresql://","postgresql+psycopg://",1)
    SQLALCHEMY_TRACK_MODIFICATIONS=False
    RATELIMIT_STORAGE_URI=os.getenv("RATELIMIT_STORAGE_URI", "memory://")
    SESSION_COOKIE_HTTPONLY=True
    SESSION_COOKIE_SAMESITE="Lax"
    REMEMBER_COOKIE_HTTPONLY=True
class DevelopmentConfig(BaseConfig):
    DEBUG=False
    SECRET_KEY=os.getenv("SECRET_KEY","local-development-only-change-me")
class TestingConfig(BaseConfig):
    TESTING=True
    WTF_CSRF_ENABLED=False
    RATELIMIT_ENABLED=False
    SECRET_KEY="test-only-secret"
    SQLALCHEMY_DATABASE_URI="sqlite://"
class ProductionConfig(BaseConfig):
    DEBUG=False
    SESSION_COOKIE_SECURE=True
    REMEMBER_COOKIE_SECURE=True
config_by_name={"development":DevelopmentConfig,"testing":TestingConfig,"production":ProductionConfig}
