from chatglm_adapter.chatglm.signer import ChatGLMSigner, TimestampProvider


def test_signer_matches_documented_formula():
    signer = ChatGLMSigner("secret", TimestampProvider("unix_ms"))
    assert signer.sign("1700000000000", "nonce") == "9e33b153c2430c70b0fcd58cfc488740"


def test_signer_headers_can_use_fixture_nonce():
    signer = ChatGLMSigner("secret", TimestampProvider("unix_ms"))
    headers = signer.new_headers(nonce="nonce")
    assert headers["X-Nonce"] == "nonce"
    assert headers["X-Sign"] == signer.sign(headers["X-Timestamp"], "nonce")


def test_chatglm_checksum_timestamp_transform(monkeypatch):
    monkeypatch.setattr("chatglm_adapter.chatglm.signer.time.time", lambda: 1700000000.124)
    provider = TimestampProvider("chatglm_checksum")
    assert provider.now() == "1700000000134"
