"""
Constants for email existence checker.
"""

# SMTP Response Codes
VALID_SMTP_CODE = 250

# Retry strategies based on SMTP codes
RETRYABLE_SMTP_CODES = {
    421,  # Service not available, closing transmission channel
    450,  # Mailbox unavailable (e.g. mailbox busy)
    451,  # Local error in processing
    452,  # Insufficient system storage
    454,  # Temporary authentication failure
}

# Rate limiting codes - need longer backoff
RATE_LIMIT_CODES = {
    429,  # Too many requests (non-standard but used by some servers)
    452,  # Insufficient system storage (sometimes used for rate limiting)
    454,  # Temporary authentication failure (sometimes rate limiting)
}

# Permanent failure codes - no retry needed
PERMANENT_FAILURE_CODES = {
    500,  # Syntax error, command unrecognized
    501,  # Syntax error in parameters or arguments
    502,  # Command not implemented
    503,  # Bad sequence of commands
    504,  # Command parameter not implemented
    550,  # Mailbox unavailable (permanent)
    551,  # User not local
    552,  # Exceeded storage allocation
    553,  # Mailbox name not allowed
    554,  # Transaction failed
}

# Default delays (in seconds)
DEFAULT_RETRY_DELAY = 2
RATE_LIMIT_DELAY = 30
MAX_RETRY_DELAY = 60

# Checkpoint settings
CHECKPOINT_INTERVAL = 100  # Save checkpoint every N emails
CHECKPOINT_FILE = "checkpoint.json"
