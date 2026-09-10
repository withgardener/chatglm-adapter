from chatglm_adapter.security.redaction import redact, redact_text


def test_redacts_bearer_jwt_and_secret_headers():
    token = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.signature"
    assert "signature" not in redact_text(f"Bearer {token}")
    assert redact({"Authorization": f"Bearer {token}", "prompt": "hello"})["Authorization"] == "<REDACTED>"


def test_does_not_redact_safe_metric_fields():
    assert redact({"model": "chatglm-glm-5.3-flash", "stream": True}) == {
        "model": "chatglm-glm-5.3-flash",
        "stream": True,
    }
