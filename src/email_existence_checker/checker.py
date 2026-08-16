"""Email existence checker with SMTP validation."""

import asyncio
import contextlib
import sys
from collections import defaultdict
from textwrap import dedent
from typing import Any

from email_validator import EmailNotValidError, validate_email

from email_existence_checker.checkpoint import CheckpointManager
from email_existence_checker.constants import (
    RATE_LIMIT_CODES,
    RATE_LIMIT_DELAY,
    RETRYABLE_SMTP_CODES,
    VALID_SMTP_CODE,
)
from email_existence_checker.exceptions import RateLimitError, TemporaryError
from email_existence_checker.models import EmailTask
from email_existence_checker.pool import DomainConnectionPool
from email_existence_checker.rate_limiter import RateLimiter


class EmailChecker:
    """Asynchronous email validator using SMTP with domain-based connection pools."""

    __slots__ = (
        "_logged_domains",
        "checkpoint_interval",
        "checkpoint_manager",
        "dry_run",
        "enable_rate_limiting",
        "failed",
        "lock",
        "max_connections",
        "max_retries",
        "pools",
        "processed_emails",
        "queues",
        "rate_limiter",
        "results",
        "timeout",
        "total_processed",
        "verbose",
        "workers_per_domain",
    )

    def __init__(
        self,
        max_connections: int = 5,
        max_retries: int = 3,
        requests_per_second: float = 10.0,
        timeout: int = 30,
        workers_per_domain: int = 10,
        checkpoint_file: str = "checkpoint.json",
        checkpoint_interval: int = 100,
        *,
        dry_run: bool = False,
        enable_rate_limiting: bool = True,
        verbose: bool = True,
    ):
        """Initialize email checker.

        Args:
            max_retries: Maximum retry attempts per email
            max_connections: Maximum SMTP connections per domain
            workers_per_domain: Number of concurrent workers per domain
            timeout: SMTP connection timeout in seconds
            verbose: Enable verbose output
            enable_rate_limiting: Enable adaptive rate limiting
            requests_per_second: Max requests per second per domain
            checkpoint_interval: Save checkpoint every N emails
            checkpoint_file: Path to checkpoint file
            dry_run: Enable dry-run mode (validate format only, no SMTP)
        """
        self.max_retries = max_retries
        self.max_connections = max_connections
        self.workers_per_domain = workers_per_domain
        self.timeout = timeout
        self.verbose = verbose
        self.enable_rate_limiting = enable_rate_limiting
        self.dry_run = dry_run
        self.checkpoint_interval = checkpoint_interval
        self.pools: dict[str, DomainConnectionPool] = {}
        self.queues: dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)
        self.results = []
        self.failed = []
        self.total_processed = 0
        self.processed_emails = set()
        self.lock = asyncio.Lock()
        self._logged_domains = set()

        # Rate limiter
        if enable_rate_limiting:
            self.rate_limiter = RateLimiter(
                requests_per_second=requests_per_second,
                burst_size=20,
                rate_limit_cooldown=30,
            )
        else:
            self.rate_limiter = None

        # Checkpoint manager
        self.checkpoint_manager = CheckpointManager(checkpoint_file)

    def _log(self, message: str) -> None:
        """Print message if verbose mode is enabled."""
        if self.verbose:
            try:
                print(message)
            except UnicodeEncodeError:
                encoding = sys.stdout.encoding or "utf-8"
                print(message.encode(encoding, errors="replace").decode(encoding))

    async def get_or_create_pool(self, domain: str) -> DomainConnectionPool:
        """Get existing pool or create new one for domain.

        Args:
            domain: Email domain

        Returns:
            Connection pool for the domain

        Raises:
            Exception: If pool initialization fails
        """
        if domain not in self.pools:
            async with self.lock:
                if domain not in self.pools:
                    pool = DomainConnectionPool(
                        domain,
                        max_connections=self.max_connections,
                        timeout=self.timeout,
                    )
                    try:
                        await pool.initialize()
                        self.pools[domain] = pool
                        if domain not in self._logged_domains:
                            self._log(f"[{domain}] MX Server: {pool.mx_host}")
                            self._logged_domains.add(domain)
                    except Exception as e:
                        raise Exception(f"Failed to initialize pool for {domain}") from e
        return self.pools[domain]

    async def check_email(self, task: EmailTask, pool: DomainConnectionPool) -> dict[str, Any]:
        """Validate a single email address via SMTP.

        Args:
            task: Email validation task
            pool: Connection pool for the email's domain

        Returns:
            Validation result dictionary

        Raises:
            TemporaryError: If validation needs retry
            RateLimitError: If rate limit is hit
        """
        email = task.email
        domain = email.split("@")[1]
        from_email = f"no-reply@{domain}"

        # Dry-run mode: validate format only
        if self.dry_run:
            try:
                valid = validate_email(email, check_deliverability=False)
                email = valid.normalized
                status_icon = "✓"
                self._log(f"[{status_icon}] [DRY-RUN] [{domain}] {email:40} Format OK")
                return {
                    "email": email,
                    "is_valid": True,
                    "smtp_code": None,
                    "smtp_message": "Format validation only (dry-run)",
                    "attempts": 1,
                    "status": "dry-run",
                }
            except EmailNotValidError as e:
                status_icon = "✗"
                self._log(f"[{status_icon}] [DRY-RUN] [{domain}] {email:40} Format ERROR")
                return {
                    "email": email,
                    "is_valid": False,
                    "error": f"Invalid format: {e!s}",
                    "attempts": 1,
                    "status": "dry-run",
                }

        # Apply rate limiting
        if self.rate_limiter:
            await self.rate_limiter.acquire(domain)

        conn = None
        try:
            valid = validate_email(email)
            email = valid.normalized

            conn = await pool.get_connection()

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, conn.mail, from_email)
            code, message = await loop.run_in_executor(None, conn.rcpt, email)

            result = {
                "email": email,
                "is_valid": code == VALID_SMTP_CODE,
                "smtp_code": code,
                "smtp_message": message.decode() if isinstance(message, bytes) else message,
                "attempts": task.attempt + 1,
                "status": "success",
            }

            # Check for rate limiting
            if code in RATE_LIMIT_CODES:
                self._log(f"[⚠] [{domain}] Rate limit detected (SMTP:{code})")
                if self.rate_limiter:
                    await self.rate_limiter.report_rate_limit(domain, RATE_LIMIT_DELAY)
                raise RateLimitError(
                    f"Rate limit hit for {domain}",
                    domain=domain,
                    retry_after=RATE_LIMIT_DELAY,
                )

            # Check for other retryable errors
            if code in RETRYABLE_SMTP_CODES:
                self._log(f"[↻] [{domain}] Temporary error (SMTP:{code})")
                raise TemporaryError(
                    f"Temporary SMTP error: {code}",
                    smtp_code=code,
                )

            # Success - report to rate limiter
            if self.rate_limiter and code == VALID_SMTP_CODE:
                await self.rate_limiter.report_success(domain)

            status_icon = "✓" if result["is_valid"] else "✗"
            self._log(f"[{status_icon}] [{domain}] {email:40} SMTP:{code}")

            await pool.return_connection(conn)
            return result

        except EmailNotValidError as e:
            if conn:
                await pool.return_connection(conn)
            return {
                "email": email,
                "is_valid": False,
                "error": f"Invalid format: {e!s}",
                "attempts": task.attempt + 1,
                "status": "failed",
            }
        except (RateLimitError, TemporaryError):
            if conn:
                with contextlib.suppress(Exception):
                    conn.quit()
            raise
        except Exception as e:
            if conn:
                with contextlib.suppress(Exception):
                    conn.quit()

            # Check if it's worth retrying
            error_str = str(e).lower()
            if any(word in error_str for word in ["timeout", "connection", "network"]):  # noqa: SIM102
                if task.attempt < self.max_retries:
                    delay = min(2**task.attempt, 10)
                    await asyncio.sleep(delay)
                    task.attempt += 1
                    task.last_error = str(e)
                    raise TemporaryError(f"Connection error: {e!s}") from e

            return {
                "email": email,
                "is_valid": False,
                "error": str(e),
                "attempts": task.attempt + 1,
                "status": "failed_max_retries",
            }

    async def _worker(self, domain: str, worker_id: int) -> None:
        """Worker coroutine to process emails for a specific domain.

        Args:
            domain: Email domain to process
            worker_id: Worker identifier
        """
        queue = self.queues[domain]

        # Skip pool initialization in dry-run mode
        pool = None
        if not self.dry_run:
            try:
                pool = await self.get_or_create_pool(domain)
            except Exception as e:
                if domain not in self._logged_domains:
                    self._log(f"[{domain}] Pool init failed: {e!s}")
                    self._logged_domains.add(domain)

                while not queue.empty():
                    try:
                        task = queue.get_nowait()
                        async with self.lock:
                            self.failed.append({
                                "email": task.email,
                                "error": f"Pool initialization failed: {e!s}",
                                "status": "failed",
                            })
                            self.total_processed += 1
                        queue.task_done()
                    except asyncio.QueueEmpty:
                        break
                return

        while True:
            try:
                task = await queue.get()

                try:
                    attempt_str = f"try:{task.attempt + 1}" if task.attempt > 0 else "try:1"
                    self._log(f"[>] [{domain}] {task.email:40} [{attempt_str}]")
                    result = await self.check_email(task, pool)
                    async with self.lock:
                        self.results.append(result)
                        self.processed_emails.add(task.email)
                        self.total_processed += 1

                        # Save checkpoint periodically
                        if self.total_processed % self.checkpoint_interval == 0:
                            self._save_checkpoint_sync()

                        if self.total_processed % 10 == 0:
                            valid_count = len([r for r in self.results if r.get("is_valid")])
                            self._log(f"\n[===] Progress: {self.total_processed} processed | {valid_count} valid\n")
                except (RateLimitError, TemporaryError) as e:
                    # Retry on temporary errors
                    if task.attempt < self.max_retries:
                        # For rate limiting, use custom backoff
                        if isinstance(e, RateLimitError):
                            delay = e.retry_after
                            self._log(f"[⏳] [{domain}] Waiting {delay}s due to rate limit")
                        else:
                            delay = min(2**task.attempt, 30)

                        await asyncio.sleep(delay)
                        task.attempt += 1
                        await queue.put(task)
                    else:
                        async with self.lock:
                            self.failed.append({
                                "email": task.email,
                                "error": str(e),
                                "attempts": task.attempt,
                                "status": "failed_max_retries",
                            })
                            self.total_processed += 1
                            self._log(f"[✗] [{domain}] {task.email:40} FAILED: {str(e)[:30]}")
                except Exception as e:
                    if task.attempt < self.max_retries:
                        task.attempt += 1
                        await queue.put(task)
                    else:
                        async with self.lock:
                            self.failed.append({
                                "email": task.email,
                                "error": str(e),
                                "attempts": task.attempt,
                                "status": "failed_max_retries",
                            })
                            self.total_processed += 1
                            self._log(f"[✗] [{domain}] {task.email:40} FAILED: {str(e)[:30]}")

                queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._log(f"[{domain}] Worker error: {e!s}")
                queue.task_done()

    def _save_checkpoint_sync(self) -> None:
        """Save checkpoint synchronously (called from async context)."""
        pending = []
        for _domain, queue in self.queues.items():
            pending.extend([task.email for task in list(queue._queue)])

        self.checkpoint_manager.save_checkpoint(
            processed_emails=list(self.processed_emails),
            results=self.results,
            failed=self.failed,
            pending_emails=pending,
            stats={
                "total_processed": self.total_processed,
                "rate_limiter_stats": self.rate_limiter.get_all_stats() if self.rate_limiter else {},
            },
        )
        self._log(f"[💾] Checkpoint saved ({self.total_processed} processed)")

    async def process_emails(self, email_list: list[str], *, resume: bool = False) -> dict[str, Any]:
        """Process a list of emails using domain-based queues and connection pools.

        Args:
            email_list: List of email addresses to validate
            resume: Resume from checkpoint if available

        Returns:
            Dictionary with validation results and statistics
        """
        # Check for resume
        if resume and self.checkpoint_manager.has_checkpoint():
            checkpoint = self.checkpoint_manager.load_checkpoint()
            if checkpoint:
                self._log("[🔄] Resuming from checkpoint...")
                self.processed_emails = set(checkpoint.get("processed_emails", []))
                self.results = checkpoint.get("results", [])
                self.failed = checkpoint.get("failed", [])
                self.total_processed = len(self.processed_emails)

                # Filter out already processed emails
                email_list = [e for e in email_list if e not in self.processed_emails]
                self._log(f"[📋] {len(email_list)} emails remaining to process")

        if not email_list:
            self._log("[✓] All emails already processed!")
            return {
                "total": len(self.processed_emails),
                "processed": self.total_processed,
                "valid": len([r for r in self.results if r.get("is_valid")]),
                "invalid": len(self.failed) + len([r for r in self.results if not r.get("is_valid")]),
                "results": self.results,
                "failed": self.failed,
            }

        # Group emails by domain
        domain_groups = defaultdict(list)
        for email in email_list:
            try:
                domain = email.strip().split("@")[1]
                domain_groups[domain].append(email.strip())
            except Exception:
                self.failed.append({
                    "email": email,
                    "error": "Invalid email format",
                    "status": "failed",
                })

        self._log(dedent(
            f"""
            Starting Email Validation
            -------------------------
            Total Emails   : {len(email_list)}
            Unique Domains : {len(domain_groups)}
            Dry-Run Mode   : {'Enabled' if self.dry_run else 'Disabled'}
            Rate Limiting  : {'Enabled' if self.enable_rate_limiting else 'Disabled'}
            Checkpoints    : Every {self.checkpoint_interval} emails

            :: Domains Detail ::"""
        ))  # fmt: skip

        for domain, emails in domain_groups.items():
            self._log(f" - {domain:25} {len(emails):3} emails")

        # Queue emails
        for domain, emails in domain_groups.items():
            for email in emails:
                await self.queues[domain].put(EmailTask(email=email))

        # Start workers
        workers = []
        for domain in domain_groups:
            worker_count = min(self.workers_per_domain, len(domain_groups[domain]))
            for worker_id in range(worker_count):
                worker = asyncio.create_task(self._worker(domain, worker_id))
                workers.append(worker)

        self._log(f"\nStarted {len(workers)} workers across {len(domain_groups)} domains\n")

        # Process all emails
        try:
            await asyncio.wait_for(
                asyncio.gather(*[queue.join() for queue in self.queues.values()]),
                timeout=300,
            )
        except TimeoutError:
            self._log("\n[WARN] Processing timeout reached (5 minutes)")
        finally:
            for worker in workers:
                worker.cancel()
            await asyncio.gather(*workers, return_exceptions=True)

            for pool in self.pools.values():
                await pool.close_all()

            # Final checkpoint save
            self._save_checkpoint_sync()

        # Summary
        successful = len([r for r in self.results if r.get("is_valid")])
        failed = len(self.failed) + len([r for r in self.results if not r.get("is_valid")])

        # Show rate limiter stats
        if self.rate_limiter:
            rate_stats = self.rate_limiter.get_all_stats()
            if rate_stats:
                self._log("\n:: Rate Limiting Stats ::")
                for domain, stats in rate_stats.items():
                    if stats.get("rate_limits_hit", 0) > 0:
                        self._log(f" - {domain:25} {stats['rate_limits_hit']} rate limits hit")

        self._log(dedent(
            f"""
            SUMMARY
            ------------------------------
            Total Emails Processed: {self.total_processed}
            Valid Emails: {successful}
            Invalid/Failed: {failed}
            """
        ))  # fmt: skip

        return {
            "total": len(email_list) + len(self.processed_emails) - self.total_processed,
            "processed": self.total_processed,
            "valid": successful,
            "invalid": failed,
            "results": self.results,
            "failed": self.failed,
            "rate_limiter_stats": self.rate_limiter.get_all_stats() if self.rate_limiter else {},
        }
