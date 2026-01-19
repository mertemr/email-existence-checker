"""Checkpoint and resume functionality for email validation."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any


class CheckpointManager:
    """Manage checkpoints for resuming interrupted validation sessions."""

    def __init__(self, checkpoint_file: str | Path = "checkpoint.json") -> None:
        """Initialize checkpoint manager.

        Args:
            checkpoint_file: Path to checkpoint file
        """
        self.checkpoint_file = Path(checkpoint_file)
        self.checkpoint_data: dict[str, Any] = {}

    def save_checkpoint(
        self,
        processed_emails: list[str],
        results: list[dict],
        failed: list[dict],
        pending_emails: list[str],
        stats: dict[str, Any] | None = None,
    ) -> None:
        """Save current progress to checkpoint file.

        Args:
            processed_emails: Emails that have been processed
            results: Validation results
            failed: Failed validations
            pending_emails: Emails still to process
            stats: Additional statistics
        """
        checkpoint = {
            "timestamp": datetime.now().isoformat(),
            "processed_emails": processed_emails,
            "pending_emails": pending_emails,
            "results": results,
            "failed": failed,
            "stats": stats or {},
        }

        with open(self.checkpoint_file, "w", encoding="utf-8") as f:
            json.dump(checkpoint, f, indent=2)

    def load_checkpoint(self) -> dict[str, Any] | None:
        """Load checkpoint from file.

        Returns:
            Checkpoint data or None if no checkpoint exists
        """
        if not self.checkpoint_file.exists():
            return None

        try:
            with open(self.checkpoint_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load checkpoint: {e}")
            return None

    def clear_checkpoint(self) -> None:
        """Delete checkpoint file."""
        if self.checkpoint_file.exists():
            self.checkpoint_file.unlink()

    def has_checkpoint(self) -> bool:
        """Check if checkpoint file exists.

        Returns:
            True if checkpoint exists
        """
        return self.checkpoint_file.exists()

    def get_pending_emails(self) -> list[str]:
        """Get list of pending emails from checkpoint.

        Returns:
            List of pending email addresses
        """
        checkpoint = self.load_checkpoint()
        if checkpoint:
            return checkpoint.get("pending_emails", [])
        return []

    def get_checkpoint_info(self) -> dict[str, Any] | None:
        """Get information about checkpoint.

        Returns:
            Checkpoint metadata or None
        """
        checkpoint = self.load_checkpoint()
        if not checkpoint:
            return None

        return {
            "timestamp": checkpoint.get("timestamp"),
            "processed_count": len(checkpoint.get("processed_emails", [])),
            "pending_count": len(checkpoint.get("pending_emails", [])),
            "results_count": len(checkpoint.get("results", [])),
            "failed_count": len(checkpoint.get("failed", [])),
        }


def save_failed_to_file(failed_emails: list[dict], output_file: str | Path = "failed_emails.txt") -> None:
    """Save failed emails to separate file for retry.

    Args:
        failed_emails: List of failed email validation results
        output_file: Path to output file
    """
    output_path = Path(output_file)
    with open(output_path, "w", encoding="utf-8") as f:
        for item in failed_emails:
            email = item.get("email", "")
            error = item.get("error", "unknown")
            f.write(f"{email}\t# Error: {error}\n")


def load_failed_from_file(input_file: str | Path) -> list[str]:
    """Load failed emails from file for retry.

    Args:
        input_file: Path to file with failed emails

    Returns:
        List of email addresses
    """
    input_path = Path(input_file)
    if not input_path.exists():
        return []

    emails = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            # Strip comments
            email = line.split("#")[0].strip()
            if email:
                emails.append(email)

    return emails
