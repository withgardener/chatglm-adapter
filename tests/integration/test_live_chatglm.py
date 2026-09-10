import os

import pytest


@pytest.mark.skipif(
    os.getenv("CHATGLM_LIVE_TEST") != "1",
    reason="requires an explicitly enabled self-owned ChatGLM live test environment",
)
def test_live_chatglm_requires_current_har_contract():
    pytest.fail("Implement only after current HAR endpoint and SSE fixtures are checked in.")

