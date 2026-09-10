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
) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "App-Name": "chatglm",
        "X-Lang": "zh",
        "X-Device-Id": device_id,
        "X-App-Platform": "pc",
        "X-App-Version": "0.0.1",
        "X-Request-Id": request_id or str(uuid4()),
    }
    headers.update(signer.new_headers(nonce=nonce))
    return headers

