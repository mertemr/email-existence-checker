"""
Example usage scenarios for email-existence-checker
"""

from email_existence_checker import (
    EmailChecker,
    read_emails_from_file,
    write_results_to_file,
)


# Example 1: Basic validation
async def basic_validation():
    """Simple email validation example."""
    checker = EmailChecker(verbose=True)

    emails = ["user@example.com", "test@gmail.com"]

    results = await checker.process_emails(emails)

    print(f"Valid: {results['valid']}")
    print(f"Invalid: {results['invalid']}")


# Example 2: With rate limiting
async def with_rate_limiting():
    """Email validation with rate limiting."""
    checker = EmailChecker(
        enable_rate_limiting=True,
        requests_per_second=5.0,  # 5 requests per second per domain
        max_retries=5,
        verbose=True,
    )

    emails = read_emails_from_file("emails.txt")

    results = await checker.process_emails(emails)

    # Check rate limiter stats
    for domain, stats in results.get("rate_limiter_stats", {}).items():
        if stats.get("rate_limits_hit", 0) > 0:
            print(f"⚠ {domain}: Hit rate limit {stats['rate_limits_hit']} times")


# Example 3: With checkpoints (resume capability)
async def with_checkpoints():
    """Email validation with checkpoint support."""
    checker = EmailChecker(
        checkpoint_interval=50,  # Save every 50 emails
        checkpoint_file="my_checkpoint.json",
        verbose=True,
    )

    emails = read_emails_from_file("large_list.csv")

    # First run (might be interrupted)
    try:
        await checker.process_emails(emails)
    except KeyboardInterrupt:
        print("\n⚠ Interrupted! Progress saved to checkpoint.")
        return

    # Resume from checkpoint (run this after interruption)
    # results = await checker.process_emails(emails, resume=True)


# Example 4: Read CSV, output JSON
async def csv_to_json():
    """Read emails from CSV and save results as JSON."""
    checker = EmailChecker(verbose=False)

    # Read from CSV (auto-detects 'email' column)
    emails = read_emails_from_file("emails.csv")

    validation_results = await checker.process_emails(emails)

    # Save as JSON
    output_data = {
        "total": validation_results["total"],
        "valid": validation_results["valid"],
        "invalid": validation_results["invalid"],
        "results": validation_results["results"],
        "failed": validation_results["failed"],
    }

    write_results_to_file("results.json", output_data)


# Example 5: Batch processing with error handling
async def batch_with_error_handling():
    """Process large batch with comprehensive error handling."""
    checker = EmailChecker(
        max_retries=3,
        max_connections=10,
        workers_per_domain=20,
        enable_rate_limiting=True,
        requests_per_second=8.0,
        checkpoint_interval=100,
        timeout=45,
        verbose=True,
    )

    emails = read_emails_from_file("10k_emails.txt")

    results = await checker.process_emails(emails, resume=True)

    # Save successful validations
    write_results_to_file("valid_emails.csv", results, format="csv")

    # Save failed emails for retry
    if results["failed"]:
        from email_existence_checker.checkpoint import save_failed_to_file

        save_failed_to_file(results["failed"], "failed_retry.txt")
        print(f"⚠ {len(results['failed'])} emails failed - saved to failed_retry.txt")

    # Show summary
    print(f"\n✓ Processed: {results['processed']}")
    print(f"✓ Valid: {results['valid']}")
    print(f"✗ Invalid: {results['invalid']}")

    # Show domains with rate limiting issues
    rate_stats = results.get("rate_limiter_stats", {})
    problematic_domains = [
        domain
        for domain, stats in rate_stats.items()
        if stats.get("rate_limits_hit", 0) > 2
    ]

    if problematic_domains:
        print("\n⚠ Domains with rate limiting issues:")
        for domain in problematic_domains:
            print(f"  - {domain}")


# Example 6: Custom validation pipeline
async def custom_pipeline():
    """Custom validation pipeline with preprocessing."""
    # Load emails
    all_emails = read_emails_from_file("raw_emails.txt")

    # Preprocess: remove duplicates, normalize
    unique_emails = list(set(email.lower().strip() for email in all_emails))
    print(f"Removed {len(all_emails) - len(unique_emails)} duplicates")

    # Validate
    checker = EmailChecker(
        max_retries=3,
        enable_rate_limiting=True,
        verbose=False,  # Silent mode
    )

    results = await checker.process_emails(unique_emails)

    # Filter only valid emails
    valid_emails = [r["email"] for r in results["results"] if r["is_valid"]]

    # Save valid emails as plain text
    with open("validated_emails.txt", "w") as f:
        for email in valid_emails:
            f.write(f"{email}\n")

    print(f"✓ Saved {len(valid_emails)} valid emails")


# Example 7: Resume interrupted session
async def resume_example():
    """Resume a previously interrupted session."""
    from email_existence_checker import CheckpointManager

    checkpoint_mgr = CheckpointManager("checkpoint.json")

    # Check if checkpoint exists
    if checkpoint_mgr.has_checkpoint():
        info = checkpoint_mgr.get_checkpoint_info()
        print(f"Found checkpoint from {info['timestamp']}")
        print(f"  Processed: {info['processed_count']}")
        print(f"  Pending: {info['pending_count']}")

        # Resume processing
        checker = EmailChecker(
            checkpoint_file="checkpoint.json",
            verbose=True,
        )

        # Load original email list
        emails = read_emails_from_file("emails.txt")

        # Resume will skip already processed emails
        results = await checker.process_emails(emails, resume=True)

        # Clear checkpoint on success
        if results["processed"] == results["total"]:
            checkpoint_mgr.clear_checkpoint()
            print("✓ All emails processed, checkpoint cleared")
    else:
        print("No checkpoint found")


# Run examples
if __name__ == "__main__":
    print("=" * 60)
    print("Email Existence Checker - Examples")
    print("=" * 60)

    # Uncomment the example you want to run:

    # asyncio.run(basic_validation())
    # asyncio.run(with_rate_limiting())
    # asyncio.run(with_checkpoints())
    # asyncio.run(csv_to_json())
    # asyncio.run(batch_with_error_handling())
    # asyncio.run(custom_pipeline())
    # asyncio.run(resume_example())

    print("\nUncomment an example function to run it!")
