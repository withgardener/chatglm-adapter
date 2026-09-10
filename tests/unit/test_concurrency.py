import asyncio

import pytest

from chatglm_adapter.core.concurrency import UpstreamGate
from chatglm_adapter.core.errors import QueueTimeoutError


@pytest.mark.asyncio
async def test_gate_times_out_waiting_request():
    gate = UpstreamGate(1, 0.01)
    first = await gate.acquire()
    try:
        with pytest.raises(QueueTimeoutError):
            await gate.acquire()
    finally:
        await first.__aexit__(None, None, None)

