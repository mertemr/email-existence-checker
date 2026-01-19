"""Email Existence Checker - Asynchronous SMTP email validation.

This package provides tools to validate email addresses using SMTP
with domain-based connection pooling for efficient processing.

Example:
    >>> from email_existence_checker import EmailChecker
    >>> import asyncio
    >>>
    >>> async def check_emails():
    ...     checker = EmailChecker(max_retries=3, max_connections=5)
    ...     results = await checker.process_emails([
    ...         "user@example.com",
    ...         "test@domain.org"
    ...     ])
    ...     return results
    >>>
    >>> results = asyncio.run(check_emails())
"""

from .checker import EmailChecker
from .models import EmailTask
from .pool import DomainConnectionPool

__version__ = "1.0.0"
__all__ = ["EmailChecker", "EmailTask", "DomainConnectionPool"]
