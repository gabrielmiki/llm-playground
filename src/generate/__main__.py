"""CLI entry point for generating multi-format end-of-day reports."""

from __future__ import annotations

import argparse
from datetime import date

from src.generate.orchestrate import run_report_generation


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate multi-format end-of-day reports from cached FusedRecords"
        ),
    )
    parser.add_argument(
        "--date",
        default=date.today().isoformat(),
        help="Target date in YYYY-MM-DD format (default: today)",
    )
    args = parser.parse_args()

    result = run_report_generation(args.date)
    print(f"Report generated: {result.report_id}")
    print(f"  Text: data/processed/reports/{result.report_id}.txt")
    print(f"  JSON: data/processed/reports/{result.report_id}.json")
    print(f"  HTML: data/processed/reports/{result.report_id}.html")


if __name__ == "__main__":
    main()
