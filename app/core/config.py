from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str
    REDIS_URL: str
    SECRET_KEY: str
    FAIL_OPEN: bool = True

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()
