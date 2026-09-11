import base64
import json

from chatglm_adapter.chatglm.device import resolve_device_id
from chatglm_adapter.config import Settings


def _unsigned_jwt(payload: dict) -> str:
    def enc(value: dict) -> str:
        raw = json.dumps(value).encode("utf-8")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    return f"{enc({'alg': 'none'})}.{enc(payload)}.sig"


def test_resolve_device_id_prefers_explicit_override(tmp_path):
    settings = Settings(
        adapter_internal_api_key="k",
        chatglm_sign_secret="s",
        chatglm_device_id="explicit",
        chatglm_device_id_file=tmp_path / "device-id",
    )
    token = _unsigned_jwt({"device_id": "from-token"})
    assert resolve_device_id(settings, token) == "explicit"


def test_resolve_device_id_uses_token_claim(tmp_path):
    settings = Settings(
        adapter_internal_api_key="k",
        chatglm_sign_secret="s",
        chatglm_device_id_file=tmp_path / "device-id",
    )
    token = _unsigned_jwt({"device_id": "from-token"})
    assert resolve_device_id(settings, token) == "from-token"


def test_resolve_device_id_falls_back_to_generated_file(tmp_path):
    settings = Settings(
        adapter_internal_api_key="k",
        chatglm_sign_secret="s",
        chatglm_device_id_file=tmp_path / "device-id",
    )
    first = resolve_device_id(settings, "not-a-jwt")
    assert len(first) == 32
    assert resolve_device_id(settings) == first
