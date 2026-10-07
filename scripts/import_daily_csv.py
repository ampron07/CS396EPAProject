"""
Import CAMPD daily emissions CSV files into the daily_records table.

Usage (from the project folder):
    python scripts/import_daily_csv.py

It reads every file matching data/daily_*.csv, so put your downloads there, e.g.
    data/daily_2025_part1.csv
    data/daily_2025_part2.csv
"""
import glob
import os
import re

import pandas as pd
from sqlalchemy import text

from models import engine, DailyRecord, BASE_DIR

DATA_PATTERN = os.path.join(BASE_DIR, "data", "daily_*.csv")
CHUNK_SIZE = 100_000   # rows read and saved at a time, so memory use stays low

# CSV header names that don't simplify to our column name on their own.
RENAMES = {
    "state": "state_code",
    "sum_of_the_operating_time": "operating_time",
}

# Every column the daily_records table has (except the auto-numbered id).
TABLE_COLUMNS = [c.name for c in DailyRecord.__table__.columns if c.name != "id"]


def simplify(header):
    """'Gross Load (MWh)' -> 'gross_load'  (drops the units, makes it snake_case)."""
    header = re.sub(r"\(.*?\)", "", header)                  # remove "(MWh)"
    header = re.sub(r"[^a-z0-9]+", "_", header.lower())      # spaces/symbols -> _
    name = header.strip("_")
    return RENAMES.get(name, name)


def main():
    files = sorted(glob.glob(DATA_PATTERN))
    if not files:
        print(f"No files found matching {DATA_PATTERN}")
        return

    # Start fresh so running the script twice doesn't create duplicate rows.
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM daily_records"))

    total = 0
    for path in files:
        print(f"\nImporting {os.path.basename(path)}")
        file_rows = 0

        for i, chunk in enumerate(pd.read_csv(path, chunksize=CHUNK_SIZE, low_memory=False)):
            original_headers = list(chunk.columns)
            chunk.columns = [simplify(h) for h in original_headers]

            if i == 0:   # report how headers were matched, once per file
                print("  CSV header -> database column")
                for old, new in zip(original_headers, chunk.columns):
                    mark = "" if new in TABLE_COLUMNS else "   (not stored)"
                    print(f"    {old!r} -> {new}{mark}")
                missing = set(TABLE_COLUMNS) - set(chunk.columns) - {"year", "quarter", "month"}
                if missing:
                    print(f"  Not in this CSV (will be empty): {sorted(missing)}")

            # Work out year / quarter / month from the date.
            dates = pd.to_datetime(chunk["date"])
            chunk["date"] = dates.dt.strftime("%Y-%m-%d")
            chunk["year"] = dates.dt.year
            chunk["quarter"] = dates.dt.quarter
            chunk["month"] = dates.dt.month

            # Keep only columns the table has, then append them to the database.
            chunk = chunk[[c for c in TABLE_COLUMNS if c in chunk.columns]]
            chunk.to_sql("daily_records", engine, if_exists="append", index=False)

            file_rows += len(chunk)
            print(f"  ...{file_rows:,} rows saved")

        total += file_rows

    with engine.connect() as conn:
        in_db = conn.execute(text("SELECT COUNT(*) FROM daily_records")).scalar()
        first, last = conn.execute(text("SELECT MIN(date), MAX(date) FROM daily_records")).one()

    print(f"\nDone. Read {total:,} rows from {len(files)} file(s); database now holds {in_db:,}.")
    print(f"Dates covered: {first} to {last}")


if __name__ == "__main__":
    main()