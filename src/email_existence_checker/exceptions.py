"""
Exceptions for email existence checker.
"""


class EmailCheckerError(Exception):
    """Base exception for email checker."""


class MXLookupError(EmailCheckerError):
    """Exception raised when MX record lookup fails."""


class SMTPConnectionError(EmailCheckerError):
    """Exception raised when SMTP connection fails."""


class RateLimitError(EmailCheckerError):
    """Exception raised when rate limit is hit."""

    def __init__(self, message: str, domain: str, retry_after: int = 30):
        super().__init__(message)
        self.domain = domain
        self.retry_after = retry_after


class TemporaryError(EmailCheckerError):
    """Exception for temporary errors that should be retried."""

    def __init__(self, message: str, smtp_code: int | None = None):
        super().__init__(message)
        self.smtp_code = smtp_code
