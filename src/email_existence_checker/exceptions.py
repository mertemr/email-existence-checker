"""
Exceptions for email existence checker.
"""


class MXLookupError(Exception):
    """Exception raised when MX record lookup fails."""


class SMTPConnectionError(Exception):
    """Exception raised when SMTP connection fails."""
