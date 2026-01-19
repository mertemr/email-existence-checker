"""SMTP connection pool management for domains."""

import asyncio
import smtplib

import dns.resolver

from email_existence_checker.exceptions import MXLookupError, SMTPConnectionError


class DomainConnectionPool:
    """Connection pool for a specific domain with SMTP connections."""

    def __init__(self, domain: str, max_connections: int, timeout: int = 30) -> None:
        """Initialize connection pool for a domain.

        Args:
            domain: Email domain to create pool for
            max_connections: Maximum number of SMTP connections to maintain
            timeout: SMTP connection timeout in seconds
        """
        self.domain = domain
        self.max_connections = max_connections
        self.timeout = timeout
        self.connections: list[smtplib.SMTP] = []
        self.available: asyncio.Queue[smtplib.SMTP] = asyncio.Queue()
        self.mx_host: str | None = None
        self.lock = asyncio.Lock()
        self.connection_count = 0

    async def initialize(self) -> None:
        """Initialize the pool by resolving MX records.

        Raises:
            MXLookupError: If MX record lookup fails
        """
        try:
            mx_records = dns.resolver.resolve(self.domain, "MX")
            self.mx_host = str(mx_records[0].exchange)
        except Exception as e:
            raise MXLookupError(f"Failed to resolve MX for {self.domain}") from e

    async def get_connection(self) -> smtplib.SMTP:
        """Get an available connection from the pool.

        Returns:
            An active SMTP connection

        Raises:
            SMTPConnectionError: If unable to create or get a connection
        """
        # Try to get existing connection
        try:
            conn = self.available.get_nowait()
            try:
                conn.noop()
                return conn
            except Exception:
                self.connection_count -= 1
        except asyncio.QueueEmpty:
            pass

        # Create new connection if under limit
        async with self.lock:
            if self.connection_count < self.max_connections:
                try:
                    conn = await asyncio.get_event_loop().run_in_executor(
                        None, self._create_connection
                    )
                    self.connection_count += 1
                    self.connections.append(conn)
                    return conn
                except Exception as e:
                    raise SMTPConnectionError(
                        f"Failed to create connection for {self.domain}"
                    ) from e

        # Wait for available connection
        try:
            return await asyncio.wait_for(self.available.get(), timeout=10.0)
        except asyncio.TimeoutError as e:
            raise SMTPConnectionError(
                f"Timeout waiting for connection for {self.domain}"
            ) from e

    def _create_connection(self) -> smtplib.SMTP:
        """Create a new SMTP connection.

        Returns:
            A new SMTP connection instance
        """
        server = smtplib.SMTP(self.mx_host, port=25, timeout=self.timeout)
        server.set_debuglevel(0)
        server.ehlo(self.domain)
        return server

    async def return_connection(self, conn: smtplib.SMTP) -> None:
        """Return a connection to the pool.

        Args:
            conn: SMTP connection to return to the pool
        """
        try:
            await self.available.put(conn)
        except Exception:
            self.connection_count -= 1

    async def close_all(self) -> None:
        """Close all connections in the pool."""
        for conn in self.connections:
            try:
                conn.quit()
            except Exception:
                pass
