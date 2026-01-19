"""File I/O handlers for different formats."""

import csv
import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class FileHandler(ABC):
    """Abstract base class for file handlers."""

    @staticmethod
    @abstractmethod
    def read_emails(file_path: str | Path) -> list[str]:
        """Read emails from file."""
        pass

    @staticmethod
    @abstractmethod
    def write_results(file_path: str | Path, data: dict[str, Any]) -> None:
        """Write results to file."""
        pass


class TXTHandler(FileHandler):
    """Handler for plain text files (one email per line)."""

    @staticmethod
    def read_emails(file_path: str | Path) -> list[str]:
        """Read emails from text file."""
        with open(file_path, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]

    @staticmethod
    def write_results(file_path: str | Path, data: dict[str, Any]) -> None:
        """Write results to text file (valid emails only)."""
        with open(file_path, "w", encoding="utf-8") as f:
            for result in data.get("results", []):
                if result.get("is_valid"):
                    f.write(f"{result['email']}\n")


class CSVHandler(FileHandler):
    """Handler for CSV files."""

    @staticmethod
    def read_emails(file_path: str | Path) -> list[str]:
        """Read emails from CSV file.

        Expects CSV with 'email' column or reads first column.
        """
        emails = []
        with open(file_path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            if "email" in reader.fieldnames:
                emails = [row["email"].strip() for row in reader if row.get("email")]
            else:
                # Fallback: read first column
                f.seek(0)
                plain_reader = csv.reader(f)
                emails = [row[0].strip() for row in plain_reader if row and row[0].strip()]
        return emails

    @staticmethod
    def write_results(file_path: str | Path, data: dict[str, Any]) -> None:
        """Write results to CSV file."""
        with open(file_path, "w", encoding="utf-8", newline="") as f:
            fieldnames = [
                "email",
                "is_valid",
                "smtp_code",
                "smtp_message",
                "status",
                "attempts",
                "error",
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for result in data.get("results", []):
                writer.writerow({
                    "email": result.get("email", ""),
                    "is_valid": result.get("is_valid", False),
                    "smtp_code": result.get("smtp_code", ""),
                    "smtp_message": result.get("smtp_message", ""),
                    "status": result.get("status", ""),
                    "attempts": result.get("attempts", 0),
                    "error": result.get("error", ""),
                })

            # Add failed emails
            for failed in data.get("failed", []):
                writer.writerow({
                    "email": failed.get("email", ""),
                    "is_valid": False,
                    "smtp_code": "",
                    "smtp_message": "",
                    "status": failed.get("status", "failed"),
                    "attempts": failed.get("attempts", 0),
                    "error": failed.get("error", ""),
                })


class JSONHandler(FileHandler):
    """Handler for JSON files."""

    @staticmethod
    def read_emails(file_path: str | Path) -> list[str]:
        """Read emails from JSON file.

        Expects JSON array of strings or objects with 'email' field.
        """
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            if all(isinstance(item, str) for item in data):
                return data
            elif all(isinstance(item, dict) for item in data):
                return [item["email"] for item in data if "email" in item]

        raise ValueError("JSON must be array of strings or objects with 'email' field")

    @staticmethod
    def write_results(file_path: str | Path, data: dict[str, Any]) -> None:
        """Write results to JSON file."""
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


def get_file_handler(file_path: str | Path) -> FileHandler:
    """Get appropriate file handler based on extension.

    Args:
        file_path: Path to file

    Returns:
        File handler instance

    Raises:
        ValueError: If file format is not supported
    """
    path = Path(file_path)
    extension = path.suffix.lower()

    handlers: dict[str, type[FileHandler]] = {
        ".txt": TXTHandler,
        ".csv": CSVHandler,
        ".json": JSONHandler,
    }

    handler_class = handlers.get(extension)
    if not handler_class:
        raise ValueError(f"Unsupported file format: {extension}. Supported formats: {', '.join(handlers.keys())}")

    return handler_class()


def read_emails_from_file(file_path: str | Path) -> list[str]:
    """Read emails from file (auto-detect format).

    Args:
        file_path: Path to input file

    Returns:
        List of email addresses
    """
    handler = get_file_handler(file_path)
    return handler.read_emails(file_path)


def write_results_to_file(file_path: str | Path, data: dict[str, Any], format: str | None = None) -> None:
    """Write results to file.

    Args:
        file_path: Path to output file
        data: Results data
        format: Force specific format (txt, csv, json), or auto-detect from extension
    """
    if format:
        file_path = Path(file_path).with_suffix(f".{format.lower()}")

    handler = get_file_handler(file_path)
    handler.write_results(file_path, data)
