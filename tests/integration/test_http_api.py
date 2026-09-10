from fastapi.testclient import TestClient

from chatglm_adapter.chatglm.sse_parser import RawSSEEvent


class FakeChatGLM:
    async def stream(self, request, builder, *, request_id):
        yield RawSSEEvent("message", '{"reasoning_content":"think"}')
        yield RawSSEEvent("message", '{"content":"answer"}')
        yield RawSSEEvent(None, "[DONE]")


def test_health_models_and_auth_boundary(monkeypatch, tmp_path):
    monkeypatch.setenv("ADAPTER_INTERNAL_API_KEY", "k" * 32)
    monkeypatch.setenv("CHATGLM_SIGN_SECRET", "s" * 32)
    monkeypatch.setenv("CHATGLM_DEVICE_ID_FILE", str(tmp_path / "device-id"))
    monkeypatch.setenv("CHATGLM_REFRESH_TOKEN_FILE", str(tmp_path / "refresh-token"))

    from chatglm_adapter.config import get_settings

    get_settings.cache_clear()
    from chatglm_adapter.main import app

    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/health").json()["queue_depth"] == 0
        assert client.get("/v1/models").status_code == 401

        response = client.get(
            "/v1/models",
            headers={"Authorization": "Bearer " + "k" * 32},
        )
        assert response.status_code == 200
        assert response.json()["data"][0]["id"] == "chatglm-glm-5.3-flash"

        app.state.container.chatglm = FakeChatGLM()
        payload = {
            "model": "chatglm-glm-5.3-flash",
            "messages": [{"role": "user", "content": "hello"}],
        }
        response = client.post(
            "/v1/chat/completions",
            headers={"Authorization": "Bearer " + "k" * 32},
            json=payload,
        )
        assert response.status_code == 200
        assert response.json()["choices"][0]["message"]["content"] == "answer"
        assert response.json()["choices"][0]["message"]["reasoning_content"] == "think"

        response = client.post(
            "/v1/chat/completions",
            headers={"Authorization": "Bearer " + "k" * 32},
            json={**payload, "stream": True},
        )
        assert response.status_code == 200
        assert '"content":"answer"' in response.text
        assert response.text.endswith("data: [DONE]\n\n")
