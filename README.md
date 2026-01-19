# Email Existence Checker

Asynchronous email validator using SMTP with domain-based connection pooling, intelligent rate limiting, and checkpoint support for high-performance email verification.

## ✨ Features

- ⚡ **High Performance**: Asynchronous processing with domain-based connection pooling
- 🧠 **Smart Retry Logic**: SMTP code-aware retry with exponential backoff
- 🛡️ **Rate Limiting**: Adaptive throttling prevents server blocks (especially for Outlook, Gmail)
- 💾 **Checkpoint & Resume**: Auto-save progress, resume interrupted sessions
- 📁 **Multi-Format Support**: Read/write TXT, CSV, JSON formats
- 🌐 **Domain-Aware**: Groups emails by domain for efficient SMTP connections
- 📊 **Detailed Analytics**: Comprehensive validation results with statistics
- 🎯 **Dual Interface**: Use as CLI tool or Python library
- 🔌 **Connection Management**: Configurable connection pools per domain

## Installation

### From PyPI (once published)

```bash
pip install email-existence-checker
```

### From source with uv

```bash
# Clone the repository
git clone https://github.com/mertemr/email-existence-checker.git
cd email-existence-checker

# Install with uv
uv pip install -e .
```

## Usage

### As a Command-Line Tool

```bash
# Basic usage
email-checker -f emails.txt

# With rate limiting and checkpoints (recommended for large batches)
email-checker -f emails.txt \
  --requests-per-second 5 \
  --checkpoint-interval 100 \
  --save-failed failed.txt

# Resume interrupted session
email-checker -f emails.txt --resume

# CSV input/output
email-checker -f emails.csv -o results.csv

# Quiet mode
email-checker -f emails.txt -q
```

#### CLI Options

```
-f, --file FILE              Input file (supports .txt, .csv, .json) [required]
-o, --output OUTPUT          Output file (format auto-detected)
--output-format FORMAT       Force output format (json/csv/txt)
-w, --workers N              Workers per domain (default: 10)
-r, --max-retries N          Max retry attempts (default: 5)
--max-connections N          Max SMTP connections per domain (default: 5)
--timeout N                  SMTP timeout in seconds (default: 30)
--requests-per-second N      Max requests/sec per domain (default: 10.0)
--disable-rate-limiting      Disable adaptive rate limiting
--checkpoint-interval N      Save checkpoint every N emails (default: 100)
--checkpoint-file FILE       Checkpoint file path (default: checkpoint.json)
--resume                     Resume from checkpoint
--save-failed FILE           Save failed emails separately
-q, --quiet                  Suppress verbose output
```

### As a Python Library

```python
import asyncio
from email_existence_checker import EmailChecker

async def main():
    # Create checker instance with rate limiting
    checker = EmailChecker(
        max_retries=5,
        max_connections=5,
        workers_per_domain=10,
        timeout=30,
        enable_rate_limiting=True,
        requests_per_second=10.0,
        checkpoint_interval=100,
        verbose=True
    )
    
    # Validate emails
    emails = [
        "user@example.com",
        "test@domain.org",
        "invalid@nonexistent.xyz"
    ]
    
    results = await checker.process_emails(emails)
    
    # Access results
    print(f"Total: {results['total']}")
    print(f"Valid: {results['valid']}")
    print(f"Invalid: {results['invalid']}")
    
    # Detailed results
    for result in results['results']:
        print(f"{result['email']}: {result['is_valid']}")
    
    # Check rate limiter stats
    if results.get('rate_limiter_stats'):
        for domain, stats in results['rate_limiter_stats'].items():
            if stats.get('rate_limits_hit', 0) > 0:
                print(f"⚠ {domain}: hit rate limit {stats['rate_limits_hit']} times")

# Run
asyncio.run(main())
```

#### Advanced Usage

```python
from email_existence_checker import (
    EmailChecker,
    read_emails_from_file,
    write_results_to_file,
)
import asyncio

async def validate_with_resume():
    # Read from any format (CSV, JSON, TXT)
    emails = read_emails_from_file("emails.csv")
    
    checker = EmailChecker(
        max_retries=5,
        enable_rate_limiting=True,
        requests_per_second=5.0,
        checkpoint_interval=100,
        verbose=False  # Silent mode
    )
    
    # Resume from checkpoint if exists
    results = await checker.process_emails(emails, resume=True)
    
    # Save to different formats
    write_results_to_file("results.json", results)
    write_results_to_file("results.csv", results)
    
    # Save failed for retry
    if results['failed']:
        from email_existence_checker.checkpoint import save_failed_to_file
        save_failed_to_file(results['failed'], "failed_emails.txt")
    
    return results

asyncio.run(validate_with_resume())
```

### Input File Format

**TXT (Plain Text):**
```text
user1@example.com
user2@domain.org
user3@company.com
```

**CSV:**
```csv
email,name
user1@example.com,John Doe
user2@domain.org,Jane Smith
```

**JSON:**
```json
[
  "user1@example.com",
  "user2@domain.org"
]
```

Or with metadata:
```json
[
  {"email": "user1@example.com", "name": "John"},
  {"email": "user2@domain.org", "name": "Jane"}
]
```

### Output Format

Results are saved in JSON format:

```json
{
  "total": 3,
  "processed": 3,
  "valid": 2,
  "invalid": 1,
  "elapsed_seconds": 5.23,
  "emails_per_second": 0.57,
  "results": [
    {
      "email": "user1@example.com",
      "is_valid": true,
      "smtp_code": 250,
      "smtp_message": "OK",
      "attempts": 1,
      "status": "success"
    },
    {
      "email": "invalid@domain.org",
      "is_valid": false,
      "smtp_code": 550,
      "smtp_message": "User not found",
      "attempts": 1,
      "status": "success"
    }
  ],
  "failed": []
}
```

## How It Works

1. **Domain Grouping**: Emails are grouped by domain for efficient processing
2. **MX Resolution**: Resolves MX records for each domain
3. **Connection Pooling**: Maintains reusable SMTP connections per domain
4. **Rate Limiting**: Monitors SMTP responses and adjusts request rate
5. **Concurrent Workers**: Multiple workers process emails simultaneously per domain
6. **SMTP Verification**: Validates emails using SMTP RCPT TO command
7. **Smart Retry**: Failed validations are retried based on SMTP error codes
8. **Checkpoint System**: Auto-saves progress for resumable sessions

### SMTP Error Handling

The checker intelligently handles different SMTP error codes:

- **Retryable (421, 450, 451, 452)**: Temporary errors, will retry
- **Rate Limiting (429, 452, 454)**: Triggers cooldown period
- **Permanent (550, 551, 552, 553, 554)**: No retry, marked as invalid

See [ADVANCED_USAGE.md](ADVANCED_USAGE.md) for detailed information.

## Performance Tips

- **Rate Limiting**: Enable for public email providers (Gmail, Outlook, Yahoo)
- **Checkpoints**: Always use for batches > 1000 emails
- **Workers**: Increase `workers_per_domain` for faster processing (10-20)
- **Connections**: Adjust `max_connections` based on server limits (3-10)
- **Request Rate**: Conservative `requests_per_second` (3-5) prevents blocks
- **Retry**: Lower `max_retries` (2-3) for faster processing of invalid emails
- **Timeout**: Reduce `timeout` (15-30s) if servers respond quickly

### Real-World Example: 10k Outlook Emails

```bash
# Problem: Outlook blocks after ~500 requests
# Solution: Rate limiting + checkpoints

email-checker -f outlook_10k.txt \
  --requests-per-second 3 \
  --checkpoint-interval 100 \
  --save-failed failed.txt \
  --max-retries 3

# If blocked, wait 5-10 minutes then:
email-checker -f outlook_10k.txt --resume
```

See [ADVANCED_USAGE.md](ADVANCED_USAGE.md) for more scenarios.

## API Reference

### `EmailChecker`

Main class for email validation.

**Parameters:**
- `max_retries` (int): Maximum retry attempts (default: 3)
- `max_connections` (int): Max SMTP connections per domain (default: 5)
- `workers_per_domain` (int): Concurrent workers per domain (default: 10)
- `timeout` (int): SMTP connection timeout in seconds (default: 30)
- `verbose` (bool): Enable verbose output (default: True)
- `enable_rate_limiting` (bool): Enable adaptive rate limiting (default: True)
- `requests_per_second` (float): Max requests/sec per domain (default: 10.0)
- `checkpoint_interval` (int): Save checkpoint every N emails (default: 100)
- `checkpoint_file` (str): Path to checkpoint file (default: "checkpoint.json")

**Methods:**
- `async process_emails(email_list: list[str], resume: bool = False) -> dict`: Validate emails and return results

### Result Dictionary

```python
{
    "total": int,                    # Total emails to process
    "processed": int,                # Emails processed
    "valid": int,                    # Valid emails count
    "invalid": int,                  # Invalid emails count
    "results": list[dict],           # Detailed results
    "failed": list[dict],            # Failed validations
    "rate_limiter_stats": dict,      # Rate limiter statistics
}
```

### Utility Functions

- `read_emails_from_file(path)`: Read emails from TXT/CSV/JSON file
- `write_results_to_file(path, data, format=None)`: Write results in any format
- `save_failed_to_file(failed, path)`: Save failed emails for retry

## Documentation

- [ADVANCED_USAGE.md](ADVANCED_USAGE.md) - Detailed usage guide
- [CHANGELOG.md](CHANGELOG.md) - Version history and changes
- [examples.py](examples.py) - Code examples

## Development

```bash
# Clone repository
git clone https://github.com/mertemr/email-existence-checker.git
cd email-existence-checker

# Install in development mode
uv pip install -e ".[dev]"

# Run tests
pytest

# Format code
black src/
ruff check src/
```

## Building and Publishing

```bash
# Build package
uv build

# Publish to PyPI
uv publish
```

## Requirements

- Python 3.10+
- dnspython
- email-validator

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Disclaimer

This tool validates email addresses using SMTP. Some mail servers may:
- Rate limit validation requests
- Block validation attempts
- Return false positives/negatives

Use responsibly and respect server policies.
