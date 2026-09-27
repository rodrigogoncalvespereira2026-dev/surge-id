import os


def _as_bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def is_production():
    if os.environ.get("RENDER"):
        return True
    return os.environ.get("ENV", "development").strip().lower() == "production"


class Config:
    ENV = os.environ.get("ENV", "development")
    JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-me")
    JWT_EXP_DAYS = int(os.environ.get("JWT_EXP_DAYS", "30"))
    DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///surge-id.db")
    ALLOWED_ORIGINS = [
        origin.strip()
        for origin in os.environ.get("ALLOWED_ORIGINS", "*").split(",")
        if origin.strip()
    ]
    RATELIMIT_DEFAULT = os.environ.get("RATELIMIT_DEFAULT", "200/hour")
    RATELIMIT_AUTH = os.environ.get("RATELIMIT_AUTH", "10/minute")
    RATELIMIT_ENABLED = _as_bool(os.environ.get("RATELIMIT_ENABLED"), True)
    AUTO_INIT_DB = _as_bool(os.environ.get("AUTO_INIT_DB"), True)

    @classmethod
    def load(cls, app):
        app.config.from_object(cls)
        if is_production() and app.config["JWT_SECRET"] == "dev-secret-change-me":
            raise RuntimeError("JWT_SECRET tem de ser definido em produção")
