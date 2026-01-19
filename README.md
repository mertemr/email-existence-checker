# Email Existence Checker

Asynchronous email validator using SMTP with domain-based connection pooling for high-performance email verification.

## Features

- ⚡ **High Performance**: Asynchronous processing with domain-based connection pooling
- 🔄 **Smart Retry Logic**: Automatic retry with exponential backoff
- 🌐 **Domain-aware**: Groups emails by domain for efficient SMTP connections
- 📊 **Detailed Results**: Comprehensive validation results with SMTP codes
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

# With custom settings
email-checker -f emails.txt -o results.json -w 20 -r 3 --max-connections 10

# Quiet mode
email-checker -f emails.txt -q
```

#### CLI Options

```
-f, --file FILE              Input file with emails (one per line) [required]
-o, --output OUTPUT          Output JSON file (default: results.json)
-w, --workers N              Workers per domain (default: 10)
-r, --max-retries N          Max retry attempts (default: 5)
--max-connections N          Max SMTP connections per domain (default: 5)
--timeout N                  SMTP timeout in seconds (default: 30)
-q, --quiet                  Suppress verbose output
```

### As a Python Library

```python
import asyncio
from email_existence_checker import EmailChecker

async def main():
    # Create checker instance
    checker = EmailChecker(
        max_retries=3,
        max_connections=5,
        workers_per_domain=10,
        timeout=30,
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

# Run
asyncio.run(main())
```

#### Advanced Usage

```python
from email_existence_checker import EmailChecker, EmailTask
import asyncio

async def validate_with_details():
    checker = EmailChecker(
        max_retries=5,
        max_connections=10,
        workers_per_domain=20,
        timeout=45,
        verbose=False  # Silent mode
    )
    
    emails = ["user1@gmail.com", "user2@outlook.com"]
    results = await checker.process_emails(emails)
    
    # Check individual results
    for result in results['results']:
        if result['status'] == 'success':
            print(f"✓ {result['email']}")
            print(f"  SMTP Code: {result['smtp_code']}")
            print(f"  Message: {result['smtp_message']}")
        else:
            print(f"✗ {result['email']}")
            print(f"  Error: {result.get('error', 'Unknown')}")
    
    return results

asyncio.run(validate_with_details())
```

### Input File Format

Create a text file with one email per line:

```text
user1@example.com
user2@domain.org
test@company.com
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
4. **Concurrent Workers**: Multiple workers process emails simultaneously per domain
5. **SMTP Verification**: Validates emails using SMTP RCPT TO command
6. **Smart Retry**: Failed validations are retried with exponential backoff

## Performance Tips

- **Workers**: Increase `workers_per_domain` for faster processing
- **Connections**: Adjust `max_connections` based on server limits
- **Retry**: Lower `max_retries` for faster processing of invalid emails
- **Timeout**: Reduce `timeout` if servers respond quickly

## API Reference

### `EmailChecker`

Main class for email validation.

**Parameters:**
- `max_retries` (int): Maximum retry attempts (default: 3)
- `max_connections` (int): Max SMTP connections per domain (default: 5)
- `workers_per_domain` (int): Concurrent workers per domain (default: 10)
- `timeout` (int): SMTP connection timeout in seconds (default: 30)
- `verbose` (bool): Enable verbose output (default: True)

**Methods:**
- `async process_emails(email_list: list[str]) -> dict`: Validate emails and return results

### Result Dictionary

```python
{
    "total": int,           # Total emails to process
    "processed": int,       # Emails processed
    "valid": int,          # Valid emails count
    "invalid": int,        # Invalid emails count
    "results": list,       # Detailed results
    "failed": list         # Failed validations
}
```

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
