from uuid import uuid4

from ..config import Settings
from .signer import ChatGLMSigner


def build_headers(
    settings: Settings,
    signer: ChatGLMSigner,
    *,
    access_token: str,
    device_id: str,
    request_id: str | None = None,
    nonce: str | None = None,
    accept: str = "text/event-stream",
    content_type: str = "application/json",
    cookie: str | None = None,
) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": content_type,
        "Accept": accept,
        "App-Name": "chatglm",
        "X-Lang": "zh",
        "X-Device-Id": device_id,
        "X-App-Platform": "pc",
        "X-App-Version": "0.0.1",
        "X-Request-Id": request_id or str(uuid4()),
    }
    if settings.chatglm_user_agent:
        headers["User-Agent"] = settings.chatglm_user_agent
    if cookie:
        headers["Cookie"] = cookie
    optional_headers = {
        "X-App-fr": settings.chatglm_app_fr,
        "X-Exp-Groups": settings.chatglm_exp_groups,
        "X-Device-Model": settings.chatglm_device_model,
        "X-Device-Brand": settings.chatglm_device_brand,
    }
    headers.update({key: value for key, value in optional_headers.items() if value})
    headers.update(signer.new_headers(nonce=nonce))
    return headers
