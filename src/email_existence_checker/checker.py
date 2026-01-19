"""Email existence checker with SMTP validation."""

import asyncio
from collections import defaultdict
from textwrap import dedent
from typing import Any

from email_validator import EmailNotValidError, validate_email

from email_existence_checker.constants import VALID_SMTP_CODE
from email_existence_checker.models import EmailTask
from email_existence_checker.pool import DomainConnectionPool


class EmailChecker:
    """Asynchronous email validator using SMTP with domain-based connection pools."""

    __slots__ = (
        "max_retries",
        "max_connections",
        "workers_per_domain",
        "timeout",
        "pools",
        "queues",
        "results",
        "failed",
        "total_processed",
        "lock",
        "verbose",
        "_logged_domains",
    )

    def __init__(
        self,
        max_retries: int = 3,
        max_connections: int = 5,
        workers_per_domain: int = 10,
        timeout: int = 30,
        verbose: bool = True,
    ):
        """Initialize email checker.

        Args:
            max_retries: Maximum retry attempts per email
            max_connections: Maximum SMTP connections per domain
            workers_per_domain: Number of concurrent workers per domain
            timeout: SMTP connection timeout in seconds
            verbose: Enable verbose output
        """
        self.max_retries = max_retries
        self.max_connections = max_connections
        self.workers_per_domain = workers_per_domain
        self.timeout = timeout
        self.verbose = verbose
        self.pools: dict[str, DomainConnectionPool] = {}
        self.queues: dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)
        self.results = []
        self.failed = []
        self.total_processed = 0
        self.lock = asyncio.Lock()
        self._logged_domains = set()

    def _log(self, message: str) -> None:
        """Print message if verbose mode is enabled."""
        if self.verbose:
            print(message)

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
                        raise Exception(
                            f"Failed to initialize pool for {domain}: {str(e)}"
                        )
        return self.pools[domain]

    async def check_email(
        self, task: EmailTask, pool: DomainConnectionPool
    ) -> dict[str, Any]:
        """Validate a single email address via SMTP.

        Args:
            task: Email validation task
            pool: Connection pool for the email's domain

        Returns:
            Validation result dictionary

        Raises:
            Exception: If validation needs retry
        """
        email = task.email
        domain = email.split("@")[1]
        from_email = f"no-reply@{domain}"

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
                "smtp_message": message.decode()
                if isinstance(message, bytes)
                else message,
                "attempts": task.attempt + 1,
                "status": "success",
            }

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
                "error": f"Invalid format: {str(e)}",
                "attempts": task.attempt + 1,
                "status": "failed",
            }
        except Exception as e:
            if conn:
                try:
                    conn.quit()
                except Exception:
                    pass

            if task.attempt < self.max_retries:
                delay = min(2**task.attempt, 10)  # Cap at 10 seconds
                await asyncio.sleep(delay)
                task.attempt += 1
                task.last_error = str(e)
                raise Exception(f"Retry needed: {str(e)}")
            else:
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

        try:
            pool = await self.get_or_create_pool(domain)
        except Exception as e:
            if domain not in self._logged_domains:
                self._log(f"[{domain}] Pool init failed: {str(e)}")
                self._logged_domains.add(domain)

            while not queue.empty():
                try:
                    task = queue.get_nowait()
                    async with self.lock:
                        self.failed.append(
                            {
                                "email": task.email,
                                "error": f"Pool initialization failed: {str(e)}",
                                "status": "failed",
                            }
                        )
                        self.total_processed += 1
                    queue.task_done()
                except asyncio.QueueEmpty:
                    break
            return

        while True:
            try:
                task = await queue.get()

                try:
                    attempt_str = (
                        f"try:{task.attempt + 1}" if task.attempt > 0 else "try:1"
                    )
                    self._log(f"[>] [{domain}] {task.email:40} [{attempt_str}]")
                    result = await self.check_email(task, pool)
                    async with self.lock:
                        self.results.append(result)
                        self.total_processed += 1
                        if self.total_processed % 10 == 0:
                            valid_count = len(
                                [r for r in self.results if r.get("is_valid")]
                            )
                            self._log(
                                f"\n[===] Progress: {self.total_processed} processed | {valid_count} valid\n"
                            )
                except Exception as e:
                    if task.attempt < self.max_retries:
                        await queue.put(task)
                    else:
                        async with self.lock:
                            self.failed.append(
                                {
                                    "email": task.email,
                                    "error": str(e),
                                    "attempts": task.attempt,
                                    "status": "failed_max_retries",
                                }
                            )
                            self.total_processed += 1
                            self._log(
                                f"[✗] [{domain}] {task.email:40} FAILED: {str(e)[:30]}"
                            )

                queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._log(f"[{domain}] Worker error: {str(e)}")
                queue.task_done()

    async def process_emails(self, email_list: list[str]) -> dict[str, Any]:
        """Process a list of emails using domain-based queues and connection pools.

        Args:
            email_list: List of email addresses to validate

        Returns:
            Dictionary with validation results and statistics
        """
        # Group emails by domain
        domain_groups = defaultdict(list)
        for email in email_list:
            try:
                domain = email.strip().split("@")[1]
                domain_groups[domain].append(email.strip())
            except Exception:
                self.failed.append(
                    {
                        "email": email,
                        "error": "Invalid email format",
                        "status": "failed",
                    }
                )

        self._log(dedent(
            f"""
            Starting Email Validation
            -------------------------
            Total Emails   : {len(email_list)}
            Unique Domains : {len(domain_groups)}
            
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
        for domain in domain_groups.keys():
            worker_count = min(self.workers_per_domain, len(domain_groups[domain]))
            for worker_id in range(worker_count):
                worker = asyncio.create_task(self._worker(domain, worker_id))
                workers.append(worker)

        self._log(
            f"\nStarted {len(workers)} workers across {len(domain_groups)} domains\n"
        )

        # Process all emails
        try:
            await asyncio.wait_for(
                asyncio.gather(*[queue.join() for queue in self.queues.values()]),
                timeout=300,
            )
        except asyncio.TimeoutError:
            self._log("\n[WARN] Processing timeout reached (5 minutes)")
        finally:
            for worker in workers:
                worker.cancel()
            await asyncio.gather(*workers, return_exceptions=True)

            for pool in self.pools.values():
                await pool.close_all()

        # Summary
        successful = len([r for r in self.results if r.get("is_valid")])
        failed = len(self.failed) + len(
            [r for r in self.results if not r.get("is_valid")]
        )

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
            "total": len(email_list),
            "processed": self.total_processed,
            "valid": successful,
            "invalid": failed,
            "results": self.results,
            "failed": self.failed,
        }
