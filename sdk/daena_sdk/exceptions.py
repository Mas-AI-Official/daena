"""
Exception classes for Daena SDK.
"""


class DaenaAPIError(Exception):
    """Base exception for all Daena API errors."""
    
    def __init__(self, message: str, status_code: int = None, response: dict = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response = response


class DaenaAuthenticationError(DaenaAPIError):
    """Raised when authentication fails."""
    pass


class DaenaRateLimitError(DaenaAPIError):
    """Raised when rate limit is exceeded."""
    
    def __init__(self, message: str, retry_after: int = None, **kwargs):
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class DaenaNotFoundError(DaenaAPIError):
    """Raised when a resource is not found."""
    pass


class DaenaValidationError(DaenaAPIError):
    """Raised when request validation fails."""
    pass


class DaenaTimeoutError(DaenaAPIError):
    """Raised when a request times out."""
    pass

