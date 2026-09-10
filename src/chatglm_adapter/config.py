from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "chatglm-adapter"
    version: str = "0.1.0"
    log_level: str = "INFO"
    adapter_internal_api_key: str = Field(default="", repr=False)
    strict_parameters: bool = False

    chatglm_stream_url: str = "https://chatglm.cn/chatglm/backend-api/assistant/stream"
    chatglm_auth_refresh_url: str = "https://chatglm.cn/chatglm/user-api/user/refresh"
    chatglm_conversation_create_url: str = ""
    chatglm_conversation_delete_url: str = "https://chatglm.cn/chatglm/mainchat-api/conversation/delete"
    chatglm_time_sync_url: str = "https://chatglm.cn/chatglm/operation-api/config/cur_ts"
    chatglm_assistant_id: str = "65940acff94777010aa6b796"
    chatglm_app_fr: str = ""
    chatglm_exp_groups: str = ""
    chatglm_device_model: str = ""
    chatglm_device_brand: str = ""
    chatglm_sign_secret: str = Field(default="", repr=False)
    chatglm_timestamp_format: str = "chatglm_checksum"
    chatglm_model_glm_5_3_flash: str = "glm-5.3-flash"
    chatglm_refresh_token_file: Path = Path("/run/secrets/chatglm_refresh_token")
    chatglm_device_id_file: Path = Path("/data/device-id")

    upstream_max_concurrency: int = Field(default=1, ge=1)
    queue_max_wait_seconds: float = Field(default=30.0, ge=0)
    upstream_request_timeout_seconds: float = Field(default=180.0, gt=0)
    auth_refresh_skew_seconds: int = Field(default=60, ge=0)

    @property
    def public_models(self) -> dict[str, str]:
        return {"chatglm-glm-5.3-flash": self.chatglm_model_glm_5_3_flash}


@lru_cache
def get_settings() -> Settings:
    return Settings()
