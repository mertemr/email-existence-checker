"""Command-line interface for email existence checker."""

import asyncio
import time
from argparse import ArgumentParser

from email_existence_checker.checker import EmailChecker
from email_existence_checker.checkpoint import save_failed_to_file
from email_existence_checker.io_handlers import read_emails_from_file, write_results_to_file


def create_parser() -> ArgumentParser:
    """Create and configure argument parser."""
    parser = ArgumentParser(description="Asynchronous Email Validator using SMTP with Domain-based Connection Pools")

    parser.add_argument(
        "-f",
        "--file",
        metavar="FILE",
        type=str,
        required=True,
        help="Input file with emails (supports .txt, .csv, .json)",
    )

    parser.add_argument(
        "-o",
        "--output",
        metavar="OUTPUT",
        type=str,
        default="results.json",
        help="Output file for results (format auto-detected from extension)",
    )

    parser.add_argument(
        "--output-format",
        type=str,
        choices=["json", "csv", "txt"],
        help="Force specific output format (overrides file extension)",
    )

    parser.add_argument(
        "-w",
        "--workers",
        metavar="WORKERS",
        type=int,
        default=10,
        help="Number of concurrent workers per domain (default: 10)",
    )

    parser.add_argument(
        "-r",
        "--max-retries",
        metavar="RETRIES",
        type=int,
        default=5,
        help="Maximum number of retry attempts (default: 5)",
    )

    parser.add_argument(
        "--max-connections",
        type=int,
        default=5,
        help="Maximum SMTP connections per domain (default: 5)",
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="SMTP connection timeout in seconds (default: 30)",
    )

    parser.add_argument(
        "--requests-per-second",
        type=float,
        default=10.0,
        help="Max requests per second per domain (default: 10.0)",
    )

    parser.add_argument(
        "--disable-rate-limiting",
        action="store_true",
        help="Disable adaptive rate limiting",
    )

    parser.add_argument(
        "--checkpoint-interval",
        type=int,
        default=100,
        help="Save checkpoint every N emails (default: 100)",
    )

    parser.add_argument(
        "--checkpoint-file",
        type=str,
        default="checkpoint.json",
        help="Path to checkpoint file (default: checkpoint.json)",
    )

    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from checkpoint if available",
    )

    parser.add_argument(
        "--save-failed",
        type=str,
        metavar="FILE",
        help="Save failed emails to separate file for retry",
    )

    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress verbose output",
    )

    return parser


async def async_main(args) -> None:
    """Async main function for CLI."""
    try:
        emails = read_emails_from_file(args.file)
    except FileNotFoundError:
        print(f"Error: File '{args.file}' not found")
        return
    except Exception as e:
        print(f"Error reading file: {str(e)}")
        return

    if not emails:
        print("No emails found in file")
        return

    print(f"Loaded {len(emails)} emails from {args.file}")

    checker = EmailChecker(
        max_retries=args.max_retries,
        max_connections=args.max_connections,
        workers_per_domain=args.workers,
        timeout=args.timeout,
        verbose=not args.quiet,
        enable_rate_limiting=not args.disable_rate_limiting,
        requests_per_second=args.requests_per_second,
        checkpoint_interval=args.checkpoint_interval,
        checkpoint_file=args.checkpoint_file,
    )

    start_time = time.perf_counter()
    results = await checker.process_emails(emails, resume=args.resume)
    elapsed = time.perf_counter() - start_time

    output_data = {
        "total": results["total"],
        "processed": results["processed"],
        "valid": results["valid"],
        "invalid": results["invalid"],
        "elapsed_seconds": round(elapsed, 2),
        "emails_per_second": round(results["processed"] / elapsed, 2) if elapsed > 0 else 0,
        "results": results["results"],
        "failed": results["failed"],
        "rate_limiter_stats": results.get("rate_limiter_stats", {}),
    }

    try:
        write_results_to_file(
            args.output,
            output_data,
            format=args.output_format,
        )
        print(f"\n✓ Results saved to: {args.output}")
    except Exception as e:
        print(f"\n✗ Error saving results: {str(e)}")

    if args.save_failed and results["failed"]:
        try:
            save_failed_to_file(results["failed"], args.save_failed)
            print(f"✓ Failed emails saved to: {args.save_failed}")
        except Exception as e:
            print(f"✗ Error saving failed emails: {str(e)}")

    if results["processed"] == results["total"]:
        checker.checkpoint_manager.clear_checkpoint()

    print(f"\nTime elapsed    : {elapsed:.2f} seconds")
    print(f"Speed           : {results['processed'] / elapsed:.2f} emails/second")

    rate_stats = results.get("rate_limiter_stats", {})
    if rate_stats:
        total_rate_limits = sum(stats.get("rate_limits_hit", 0) for stats in rate_stats.values())
        if total_rate_limits > 0:
            print(f"⚠ Total rate limits hit: {total_rate_limits}")


def main() -> None:
    """Main entry point for CLI."""
    parser = create_parser()
    args = parser.parse_args()
    asyncio.run(async_main(args))


if __name__ == "__main__":
    main()
