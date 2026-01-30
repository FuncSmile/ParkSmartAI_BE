from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "ParkSmart AI"
    database_url: str = Field(
        default="sqlite:///./parksmart.db",
        description="SQLAlchemy database URL",
    )
    cors_origins: list[str] = ["*"]
    prediction_valid_minutes: int = 10
    websocket_broadcast_queue: int = 100

    class Config:
        env_file = ".env"


def get_settings() -> Settings:
    return Settings()
