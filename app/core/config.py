import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "CATMS Backend"
    API_V1_STR: str = "/api/v1"

    # Server Port Configuration
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000

    # MySQL / TiDB Database Configuration (Option C: Plain PyMySQL)
    DB_HOST: str = "gateway01.ap-southeast-1.prod.aws.tidbcloud.com"
    DB_PORT: int = 4000
    DB_USER: str = "4J6E1ab8gCC15PY.root"
    DB_PASSWORD: str = ""
    DB_NAME: str = "CatMS"
    DB_SSL_MODE: str = "VERIFY_IDENTITY"

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"),
        extra="ignore"
    )


settings = Settings()
