"""Import an ExtractionResult JSON file: python -m BACKEND.ingest FILE."""

import argparse
import sqlite3
from pathlib import Path

from pydantic import ValidationError

from BACKEND.database import DEFAULT_DB_PATH, EventStore
from shared.schema import ExtractionResult


def import_file(path, db_path=DEFAULT_DB_PATH):
    # Validate the entire input before even opening/initialising the database.
    result = ExtractionResult.model_validate_json(Path(path).read_text(encoding="utf-8-sig"))
    return EventStore(db_path).import_events(result.events)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    args = parser.parse_args()
    try:
        counts = import_file(args.file, args.db)
    except (OSError, ValueError, ValidationError, sqlite3.Error) as error:
        parser.exit(1, f"Import failed: {error}\n")
    print(f"Inserted: {counts['inserted']}; skipped: {counts['skipped']}")


if __name__ == "__main__":
    main()
