"""Data models for email validation."""

from dataclasses import dataclass


@dataclass
class EmailTask:
    """Represents an email validation task with retry information."""

    email: str
    attempt: int = 0
    last_error: str | None = None
