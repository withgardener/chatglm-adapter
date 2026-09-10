from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from .api.chat_completions import router as chat_router
from .api.health import router as health_router
from .api.models import router as models_router
from .chatglm.auth import AuthManager
from .chatglm.client import ChatGLMClient
from .chatglm.conversation import ConversationManager
from .chatglm.device import load_or_create_device_id
from .chatglm.signer import ChatGLMSigner, TimestampProvider
from .config import Settings, get_settings
from .core.concurrency import UpstreamGate


class Container:
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient):
        self.settings = settings
        self.http = http_client
        self.auth = AuthManager(settings, http_client)
        self.gate = UpstreamGate(
            settings.upstream_max_concurrency,
            settings.queue_max_wait_seconds,
        )
        self.device_id = load_or_create_device_id(settings.chatglm_device_id_file)
        self.signer = ChatGLMSigner(
            settings.chatglm_sign_secret,
            TimestampProvider(settings.chatglm_timestamp_format),
        )
        conversations = ConversationManager(settings, http_client)
        self.chatglm = ChatGLMClient(
            settings,
            http_client,
            self.auth,
            self.signer,
            self.device_id,
            conversations,
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    async with httpx.AsyncClient() as http_client:
        app.state.container = Container(settings, http_client)
        yield


app = FastAPI(title="chatglm-adapter", version=get_settings().version, lifespan=lifespan)
app.include_router(health_router)
app.include_router(models_router)
app.include_router(chat_router)

