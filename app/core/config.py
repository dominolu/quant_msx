from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "quant_msx"
    app_env: str = "local"
    log_level: str = "INFO"

    msx_base_url: str = "https://api9528mystks.mystonks.org"
    msx_spot_ws_url: str = "wss://api9528mystks.mystonks.org/api/v1/spot/ws"
    msx_futures_ws_url: str = "wss://api9528mystks.mystonks.org/api/v1/futures/ws"
    msx_api_key: str = ""
    msx_secret_key: str = ""
    msx_http_timeout_seconds: float = 30.0
    msx_http_retry_attempts: int = 2
    msx_http_retry_backoff_seconds: float = 0.2
    msx_http_max_connections: int = 100
    msx_http_max_keepalive_connections: int = 20
    msx_http_requests_per_second: float = 0

    database_url: str = "sqlite:///./data/quant_msx.sqlite3"
    live_trading_enabled: bool = False
    grid_demo_mode: bool = True

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
