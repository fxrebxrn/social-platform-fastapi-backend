from pydantic_settings import BaseSettings
from pydantic import ConfigDict

class Settings(BaseSettings):
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    REFRESH_TOKEN_EXPIRE_DAYS: int
    
    DATABASE_URL: str
    
    DEBUG: bool = False
    APP_ENV: str = "dev"

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    model_config = ConfigDict(env_file=".env", extra="ignore", env_file_encoding="utf-8")

settings = Settings()