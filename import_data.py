"""
CLI workbook importer.

    python import_data.py "URL Dashboard Database Testing.xlsx"

Targets the database in `DATABASE_URL` if set, otherwise the local SQLite file
(`aramco.db`). Use this for the first load and for very large workbooks that are
impractical to push through the browser Upload page.
"""

from __future__ import annotations

import sys

from lib.config import database_url
from lib.ingest import import_workbook


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2

    path = argv[1]
    print(f"Database: {database_url()}")
    print(f"Reading:  {path}")

    counts = import_workbook(path)
    total = counts.pop("_total")
    for category, n in counts.items():
        print(f"  {category}: {n:,}")
    print(f"Total loaded: {total:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
