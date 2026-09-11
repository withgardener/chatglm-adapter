import base64
import binascii
from dataclasses import dataclass

import httpx

from ..config import Settings
from ..core.errors import UnsupportedFeatureError, UpstreamError
from ..security.redaction import redact_text
from .auth import AuthManager
from .headers import build_headers
from .signer import ChatGLMSigner

_MIME_EXTENSIONS = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/gif": "gif",
    "image/webp": "webp",
}


@dataclass(frozen=True)
class UploadedImage:
    file_id: str
    image_url: str
    file_name: str
    file_size: int


def decode_data_url(url: str, *, max_bytes: int) -> tuple[bytes, str, str]:
    """Decode a data:image/...;base64 URL into (payload, file_name, mime)."""
    if not url.startswith("data:"):
        raise UnsupportedFeatureError(
            "only data: image URLs are supported; upload remote images yourself first"
        )
    header, _, encoded = url[5:].partition(",")
    media_type = header.removesuffix(";base64").strip().lower()
    if not media_type.startswith("image/") or ";base64" not in header:
        raise UnsupportedFeatureError(f"unsupported image data URL media type: {media_type!r}")
    if media_type not in _MIME_EXTENSIONS:
        raise UnsupportedFeatureError(f"unsupported image media type: {media_type}")
    try:
        payload = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise UnsupportedFeatureError("image data URL is not valid base64") from exc
    if not payload:
        raise UnsupportedFeatureError("image data URL is empty")
    if len(payload) > max_bytes:
        raise UnsupportedFeatureError("image exceeds the configured upload size limit")
    return payload, f"image.{_MIME_EXTENSIONS[media_type]}", media_type


class FileUploader:
    """Uploads images through the ChatGLM Web chat_upload endpoint.

    Protocol evidence: 2026-09-11 HAR, multipart fields file/from/assistant_id,
    response result.file_id/file_url/file_size/file_name.
    """

    def __init__(
        self,
        settings: Settings,
        client: httpx.AsyncClient,
        auth: AuthManager,
        signer: ChatGLMSigner,
        device_id: str,
    ):
        self._settings = settings
        self._client = client
        self._auth = auth
        self._signer = signer
        self._device_id = device_id

    async def upload(self, data_url: str) -> UploadedImage:
        payload, file_name, media_type = decode_data_url(
            data_url, max_bytes=self._settings.upload_max_image_bytes
        )
        token = await self._auth.get_access_token()
        headers = build_headers(
            self._settings,
            self._signer,
            access_token=token,
            device_id=self._device_id,
            accept="application/json",
            cookie=self._auth.cookie_header(token),
        )
        # httpx must generate the multipart boundary itself.
        del headers["Content-Type"]
        try:
            response = await self._client.post(
                self._settings.chatglm_upload_url,
                headers=headers,
                files={"file": (file_name, payload, media_type)},
                data={"from": "chat", "assistant_id": self._settings.chatglm_assistant_id},
                timeout=self._settings.upstream_request_timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise UpstreamError("ChatGLM image upload request failed", retryable=True) from exc
        if response.status_code >= 400:
            excerpt = redact_text(response.text)[:200]
            raise UpstreamError(
                f"ChatGLM image upload rejected ({response.status_code}): {excerpt}",
                status_code=response.status_code,
                retryable=response.status_code in {429, 500, 502, 503, 504},
            )
        try:
            result = response.json()["result"]
            return UploadedImage(
                file_id=str(result["file_id"]),
                image_url=str(result["file_url"]),
                file_name=str(result.get("file_name") or file_name),
                file_size=int(result.get("file_size") or len(payload)),
            )
        except (ValueError, KeyError, TypeError) as exc:
            raise UpstreamError("ChatGLM image upload response was not understood") from exc
