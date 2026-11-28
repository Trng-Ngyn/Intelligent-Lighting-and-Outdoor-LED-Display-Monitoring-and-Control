from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "Intelligent Lighting Core API"
    jwt_secret: str = "CHANGE_THIS_SECRET_BEFORE_DEPLOYMENT"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30
    refresh_token_days: int = 7

    # Tài khoản DEV để kiểm tra API khi migration chưa có bảng credential.
    dev_username: str = "admin"
    dev_password: str = "ChangeMe123!"
    dev_user_id: str = "00000000-0000-4000-8000-000000000001"
    dev_roles: str = "ADMIN"

    database_url: str = ""
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
