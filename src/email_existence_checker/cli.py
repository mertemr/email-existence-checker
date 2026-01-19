"""Command-line interface for email existence checker."""

import asyncio
import json
import time
from argparse import ArgumentParser
from pathlib import Path

from email_existence_checker.checker import EmailChecker


def create_parser() -> ArgumentParser:
    """Create and configure argument parser."""
    parser = ArgumentParser(
        description="Asynchronous Email Validator using SMTP with Domain-based Connection Pools"
    )

    parser.add_argument(
        "-f",
        "--file",
        metavar="FILE",
        type=str,
        required=True,
        help="File containing email addresses (one per line)",
    )

    parser.add_argument(
        "-o",
        "--output",
        metavar="OUTPUT",
        type=str,
        default="results.json",
        help="Output file for results (default: results.json)",
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
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress verbose output",
    )

    return parser


async def async_main(args) -> None:
    """Async main function for CLI."""
    # Read emails from file
    try:
        with open(args.file, "r") as f:
            emails = list(filter(None, [line.strip() for line in f.readlines()]))
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

    # Create checker and process
    checker = EmailChecker(
        max_retries=args.max_retries,
        max_connections=args.max_connections,
        workers_per_domain=args.workers,
        timeout=args.timeout,
        verbose=not args.quiet,
    )

    start_time = time.perf_counter()
    results = await checker.process_emails(emails)
    elapsed = time.perf_counter() - start_time

    # Prepare output
    output_data = {
        "total": results["total"],
        "processed": results["processed"],
        "valid": results["valid"],
        "invalid": results["invalid"],
        "elapsed_seconds": round(elapsed, 2),
        "emails_per_second": round(len(emails) / elapsed, 2) if elapsed > 0 else 0,
        "results": results["results"],
        "failed": results["failed"],
    }

    # Save results
    output_path = Path(args.output)
    with open(output_path, "w") as f:
        json.dump(output_data, f, indent=2)

    print(f"\nResults saved to: {args.output}")
    print(f"Time elapsed    : {elapsed:.2f} seconds")
    print(f"Speed           : {len(emails) / elapsed:.2f} emails/second")


def main() -> None:
    """Main entry point for CLI."""
    parser = create_parser()
    args = parser.parse_args()
    asyncio.run(async_main(args))


if __name__ == "__main__":
    main()
