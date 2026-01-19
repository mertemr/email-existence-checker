# Advanced Usage Guide

## Table of Contents
- [Smart Retry Mechanism](#smart-retry-mechanism)
- [Rate Limiting](#rate-limiting)
- [Checkpoint & Resume](#checkpoint--resume)
- [Multi-Format File Support](#multi-format-file-support)
- [Real-World Scenarios](#real-world-scenarios)

---

## Smart Retry Mechanism

The checker automatically detects SMTP response codes and applies appropriate retry strategies.

### SMTP Code Categories

**Retryable (Temporary) Errors:**
- `421` - Service not available
- `450` - Mailbox unavailable (busy)
- `451` - Local error in processing
- `452` - Insufficient system storage
- `454` - Temporary authentication failure

**Rate Limiting Codes:**
- `429` - Too many requests
- `452` - Can indicate rate limiting
- `454` - Sometimes used for rate limiting

**Permanent Failures (No Retry):**
- `550` - Mailbox unavailable (permanent)
- `551` - User not local
- `552` - Storage quota exceeded
- `553` - Mailbox name not allowed
- `554` - Transaction failed

### Example

```python
checker = EmailChecker(
    max_retries=5,  # Will retry up to 5 times for temporary errors
)
```

When rate limit is detected:
- Automatic 30-second cooldown
- Exponential backoff for retries
- Logged with ⚠ warning icon

---

## Rate Limiting

Adaptive rate limiting prevents getting blocked by mail servers.

### How It Works

1. **Per-Domain Tracking**: Each domain has independent rate limiting
2. **Adaptive Throttling**: Delay increases when rate limits are hit
3. **Success Recovery**: Delay decreases on successful requests
4. **Configurable Limits**: Set requests per second per domain

### Configuration

```python
checker = EmailChecker(
    enable_rate_limiting=True,
    requests_per_second=10.0,  # Max 10 req/sec per domain
)
```

### CLI Usage

```bash
# Conservative rate limiting
email-checker -f emails.txt --requests-per-second 5

# Disable rate limiting (not recommended)
email-checker -f emails.txt --disable-rate-limiting
```

### Stats

After processing, check rate limiter statistics:

```python
results = await checker.process_emails(emails)

for domain, stats in results['rate_limiter_stats'].items():
    print(f"{domain}:")
    print(f"  Requests: {stats['request_count']}")
    print(f"  Rate limits hit: {stats['rate_limits_hit']}")
    print(f"  Current delay: {stats['current_delay']}s")
```

---

## Checkpoint & Resume

For large batches, checkpoints allow resuming interrupted sessions.

### Auto-Save Checkpoints

```python
checker = EmailChecker(
    checkpoint_interval=100,  # Save every 100 emails
    checkpoint_file="my_checkpoint.json",
)

# Process emails (auto-saves progress)
results = await checker.process_emails(emails)
```

### Resume After Interruption

```python
# Resume from where you left off
results = await checker.process_emails(emails, resume=True)
```

### CLI Usage

```bash
# Initial run (interrupted)
email-checker -f 10k_emails.txt --checkpoint-interval 50
# ^C (Ctrl+C to interrupt)

# Resume later
email-checker -f 10k_emails.txt --resume
```

### Manual Checkpoint Management

```python
from email_existence_checker import CheckpointManager

mgr = CheckpointManager("checkpoint.json")

# Check if checkpoint exists
if mgr.has_checkpoint():
    info = mgr.get_checkpoint_info()
    print(f"Processed: {info['processed_count']}")
    print(f"Pending: {info['pending_count']}")
    
    # Get pending emails
    pending = mgr.get_pending_emails()
    
# Clear checkpoint when done
mgr.clear_checkpoint()
```

---

## Multi-Format File Support

### Supported Formats

#### TXT (Plain Text)
```text
user1@example.com
user2@domain.org
user3@test.com
```

#### CSV
```csv
email,name,company
user1@example.com,John Doe,Acme
user2@domain.org,Jane Smith,XYZ
```

Or simple single column:
```csv
user1@example.com
user2@domain.org
```

#### JSON
Array of strings:
```json
[
  "user1@example.com",
  "user2@domain.org"
]
```

Or objects with 'email' field:
```json
[
  {"email": "user1@example.com", "name": "John"},
  {"email": "user2@domain.org", "name": "Jane"}
]
```

### Reading Files

```python
from email_existence_checker import read_emails_from_file

# Auto-detect format from extension
emails = read_emails_from_file("emails.csv")
emails = read_emails_from_file("emails.json")
emails = read_emails_from_file("emails.txt")
```

### Writing Results

```python
from email_existence_checker import write_results_to_file

# Format auto-detected from extension
write_results_to_file("results.json", output_data)
write_results_to_file("results.csv", output_data)
write_results_to_file("valid_only.txt", output_data)  # Valid emails only

# Force specific format
write_results_to_file("output", output_data, format="csv")
```

---

## Real-World Scenarios

### Scenario 1: 10k Outlook Emails (Rate Limiting)

**Problem**: Outlook blocks after ~500 requests

**Solution**:
```bash
email-checker -f outlook_10k.txt \
  --requests-per-second 3 \
  --checkpoint-interval 100 \
  --save-failed failed.txt \
  --max-retries 3
```

If blocked:
1. Script saves checkpoint automatically
2. Wait 5-10 minutes
3. Resume: `email-checker -f outlook_10k.txt --resume`

### Scenario 2: Mixed Domains CSV

**Input**: `contacts.csv`
```csv
email,name
user1@gmail.com,John
user2@outlook.com,Jane
user3@yahoo.com,Bob
```

**Process**:
```bash
email-checker -f contacts.csv -o validated.csv
```

**Output**: `validated.csv` with validation results

### Scenario 3: Resume After Server Crash

```python
# Long-running job
checker = EmailChecker(checkpoint_interval=50)

try:
    results = await checker.process_emails(huge_email_list)
except Exception as e:
    print(f"Crashed: {e}")
    # Checkpoint was saved automatically!

# Later, resume:
results = await checker.process_emails(huge_email_list, resume=True)
```

### Scenario 4: Save Failed for Retry

```bash
# First attempt
email-checker -f emails.txt --save-failed failed.txt

# Retry failed emails with different settings
email-checker -f failed.txt \
  --requests-per-second 2 \
  --max-retries 10 \
  -o retry_results.json
```

### Scenario 5: Silent Batch Processing

```python
# Silent mode for cron jobs
checker = EmailChecker(verbose=False)
results = await checker.process_emails(emails)

# Only log summary
print(f"Valid: {results['valid']}, Invalid: {results['invalid']}")
```

---

## Error Handling Best Practices

### 1. Always Use Checkpoints for Large Batches

```python
if len(emails) > 1000:
    checker = EmailChecker(checkpoint_interval=100)
```

### 2. Enable Rate Limiting for Public Email Providers

```python
checker = EmailChecker(
    enable_rate_limiting=True,
    requests_per_second=5.0,  # Conservative for Gmail, Outlook
)
```

### 3. Save Failed Emails

```python
# Save for later retry
from email_existence_checker.checkpoint import save_failed_to_file

if results['failed']:
    save_failed_to_file(results['failed'], 'retry_later.txt')
```

### 4. Monitor Rate Limiter Stats

```python
rate_stats = results.get('rate_limiter_stats', {})
blocked_domains = [
    domain for domain, stats in rate_stats.items()
    if stats.get('rate_limits_hit', 0) > 5
]

if blocked_domains:
    print(f"Warning: These domains may need slower rate: {blocked_domains}")
```

---

## Performance Tuning

### For Speed
```python
checker = EmailChecker(
    workers_per_domain=20,       # More concurrent workers
    max_connections=10,          # More SMTP connections
    requests_per_second=15.0,    # Higher rate (risky!)
    max_retries=2,               # Fewer retries
)
```

### For Reliability
```python
checker = EmailChecker(
    workers_per_domain=5,        # Fewer concurrent workers
    max_connections=3,           # Fewer connections
    requests_per_second=3.0,     # Conservative rate
    max_retries=10,              # More retries
    checkpoint_interval=50,      # Frequent checkpoints
)
```

### For Corporate Email Servers
```python
checker = EmailChecker(
    timeout=60,                  # Longer timeout
    requests_per_second=2.0,     # Very conservative
    max_retries=5,
)
```
