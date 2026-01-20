"""Email Existence Checker - Asynchronous SMTP email validation.

This package provides tools to validate email addresses using SMTP
with domain-based connection pooling, rate limiting, and checkpoint support.

Example:
    >>> from email_existence_checker import EmailChecker
    >>> import asyncio
    >>>
    >>> async def check_emails():
    ...     checker = EmailChecker(
    ...         max_retries=3,
    ...         max_connections=5,
    ...         enable_rate_limiting=True,
    ...         checkpoint_interval=100
    ...     )
    ...     results = await checker.process_emails([
    ...         "user@example.com",
    ...         "test@domain.org"
    ...     ])
    ...     return results
    >>>
    >>> results = asyncio.run(check_emails())
"""

from importlib.metadata import version

from .checker import EmailChecker
from .checkpoint import CheckpointManager
from .io_handlers import read_emails_from_file, write_results_to_file
from .models import EmailTask
from .pool import DomainConnectionPool
from .rate_limiter import RateLimiter

__version__ = version("email-existence-checker")
__all__ = [
    "CheckpointManager",
    "DomainConnectionPool",
    "EmailChecker",
    "EmailTask",
    "RateLimiter",
    "read_emails_from_file",
    "write_results_to_file",
]
