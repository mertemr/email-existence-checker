"""Rate limiting and throttling for email validation."""

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass


@dataclass
class RateLimitState:
    """Track rate limiting state for a domain."""

    domain: str
    last_request_time: float = 0
    request_count: int = 0
    blocked_until: float = 0
    total_rate_limits: int = 0
    min_delay: float = 0.1  # Minimum delay between requests
    current_delay: float = 0.1  # Current delay (increases on rate limit)


class RateLimiter:
    """Rate limiter with adaptive throttling per domain."""

    def __init__(
        self,
        requests_per_second: float = 10.0,
        burst_size: int = 20,
        rate_limit_cooldown: int = 30,
    ):
        """Initialize rate limiter.

        Args:
            requests_per_second: Max requests per second per domain
            burst_size: Max burst requests before throttling
            rate_limit_cooldown: Seconds to wait after rate limit hit
        """
        self.requests_per_second = requests_per_second
        self.burst_size = burst_size
        self.rate_limit_cooldown = rate_limit_cooldown
        self.domain_states: dict[str, RateLimitState] = defaultdict(
            lambda: RateLimitState(domain="")
        )
        self.locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def acquire(self, domain: str) -> None:
        """Acquire permission to make request for domain.

        Args:
            domain: Email domain to check
        """
        async with self.locks[domain]:
            state = self.domain_states[domain]
            if not state.domain:
                state.domain = domain

            now = time.time()

            # Check if domain is blocked due to rate limiting
            if state.blocked_until > now:
                wait_time = state.blocked_until - now
                await asyncio.sleep(wait_time)

            # Calculate time since last request
            time_since_last = now - state.last_request_time
            min_interval = 1.0 / self.requests_per_second

            # Apply adaptive delay if needed
            if state.current_delay > 0:
                await asyncio.sleep(state.current_delay)

            # Enforce minimum interval
            if time_since_last < min_interval:
                await asyncio.sleep(min_interval - time_since_last)

            state.last_request_time = time.time()
            state.request_count += 1

    async def report_rate_limit(self, domain: str, cooldown: int | None = None) -> None:
        """Report that rate limit was hit for domain.

        Args:
            domain: Email domain that hit rate limit
            cooldown: Optional custom cooldown period
        """
        async with self.locks[domain]:
            state = self.domain_states[domain]
            state.total_rate_limits += 1

            # Increase delay exponentially
            state.current_delay = min(state.current_delay * 2, 10.0)
            if state.current_delay == 0:
                state.current_delay = 0.5

            # Set block period
            cooldown_time = cooldown or self.rate_limit_cooldown
            state.blocked_until = time.time() + cooldown_time

    async def report_success(self, domain: str) -> None:
        """Report successful request (reduce throttling).

        Args:
            domain: Email domain with successful request
        """
        state = self.domain_states[domain]
        # Gradually reduce delay on success
        if state.current_delay > state.min_delay:
            state.current_delay = max(state.current_delay * 0.9, state.min_delay)

    def get_domain_stats(self, domain: str) -> dict:
        """Get rate limit statistics for domain.

        Args:
            domain: Email domain

        Returns:
            Statistics dictionary
        """
        state = self.domain_states.get(domain)
        if not state:
            return {}

        return {
            "domain": domain,
            "request_count": state.request_count,
            "rate_limits_hit": state.total_rate_limits,
            "current_delay": state.current_delay,
            "is_blocked": state.blocked_until > time.time(),
        }

    def get_all_stats(self) -> dict[str, dict]:
        """Get statistics for all domains.

        Returns:
            Dictionary of domain statistics
        """
        return {
            domain: self.get_domain_stats(domain)
            for domain in self.domain_states.keys()
        }
