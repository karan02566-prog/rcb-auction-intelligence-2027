"""CLI entry point for Cricsheet ball-by-ball ingestion."""

from __future__ import annotations

import argparse

from src.ingestion.cricsheet import CRICSHEET_SOURCES, ingest_competitions


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download and extract configured Cricsheet datasets."
    )

    parser.add_argument(
        "--competition",
        action="append",
        choices=sorted(CRICSHEET_SOURCES),
        help="Competition code. Repeat to ingest multiple competitions.",
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Ingest all configured Cricsheet competitions.",
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Explicitly re-acquire an existing raw archive.",
    )

    args = parser.parse_args()

    if not args.all and not args.competition:
        parser.error("Provide --competition or --all.")

    competitions = (
        sorted(CRICSHEET_SOURCES)
        if args.all
        else args.competition
    )

    results = ingest_competitions(
        competitions,
        overwrite=args.overwrite,
    )

    for result in results:
        print(
            f"{result['competition']}: "
            f"{result['extracted_file_count']} files, "
            f"{result['extracted_bytes']} bytes, "
            f"SHA256={result['sha256']}"
        )


if __name__ == "__main__":
    main()