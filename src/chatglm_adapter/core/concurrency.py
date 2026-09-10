import asyncio

from .errors import QueueTimeoutError


class UpstreamGate:
    """A bounded async gate. It prevents unbounded waiters for a single account."""

    def __init__(self, slots: int, max_queue_wait_seconds: float):
        self._semaphore = asyncio.Semaphore(slots)
        self._max_queue_wait_seconds = max_queue_wait_seconds
        self._lock = asyncio.Lock()
        self._waiting = 0
        self._active = 0

    @property
    def depth(self) -> int:
        return self._waiting + self._active

    async def acquire(self):
        async with self._lock:
            self._waiting += 1
        try:
            await asyncio.wait_for(
                self._semaphore.acquire(), timeout=self._max_queue_wait_seconds
            )
        except TimeoutError as exc:
            async with self._lock:
                self._waiting -= 1
            raise QueueTimeoutError("upstream queue wait timed out") from exc
        async with self._lock:
            self._waiting -= 1
            self._active += 1
        return _GateLease(self)

    async def _release(self):
        async with self._lock:
            self._active -= 1
        self._semaphore.release()


class _GateLease:
    def __init__(self, gate: UpstreamGate):
        self._gate = gate

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self._gate._release()

