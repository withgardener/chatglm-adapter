class AdapterError(Exception):
    """Base class for errors that can be safely converted to an API response."""


class AuthenticationError(AdapterError):
    pass


class UnsupportedFeatureError(AdapterError):
    pass


class UpstreamError(AdapterError):
    def __init__(self, message: str, *, status_code: int | None = None, retryable: bool = False):
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


class QueueTimeoutError(AdapterError):
    pass


class ConfigurationError(AdapterError):
    pass

