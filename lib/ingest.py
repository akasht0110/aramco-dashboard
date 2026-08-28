"""
Workbook ingestion: read the source Excel file (one sheet per media type),
clean every cell as text, parse the digitized date, and load the result into
the `assets` table (full replace).

Used by both the admin Upload page and the `import_data.py` CLI.
"""

from __future__ import annotations

import json
import warnings
from typing import BinaryIO

import pandas as pd

from lib.db import COLUMN_MAP, DATA_COLUMNS, replace_all


def _clean_text_series(s: pd.Series) -> pd.Series:
    s = s.astype(str).str.strip()
    return s.replace({"nan": "", "None": "", "NaT": ""})


def load_workbook(source: str | BinaryIO) -> pd.DataFrame:
    """
    Read every sheet in the workbook and return one combined dataframe whose
    columns match `lib.db.DATA_COLUMNS`. The sheet name becomes `media_type`.
    Unknown columns are folded into a JSON string in `extra`.
    """
    with warnings.catch_warnings():
        # openpyxl warns about a few out-of-range date serials in the source data.
        warnings.simplefilter("ignore")
        xl = pd.ExcelFile(source)
        raw_frames = {
            name: pd.read_excel(xl, sheet_name=name, dtype=str)
            for name in xl.sheet_names
        }

    combined: list[pd.DataFrame] = []
    for sheet_name, raw in raw_frames.items():
        raw = raw.copy()
        raw.columns = [str(c).strip() for c in raw.columns]

        known = {h: COLUMN_MAP[h] for h in raw.columns if h in COLUMN_MAP}
        unknown = [h for h in raw.columns if h not in COLUMN_MAP]

        out = pd.DataFrame(index=raw.index)
        out["media_type"] = sheet_name

        for header, col in known.items():
            out[col] = _clean_text_series(raw[header])

        # Normalize Digitized to a strict Yes/No.
        if "digitized" in out.columns:
            norm = out["digitized"].str.strip().str.title()
            out["digitized"] = norm.where(norm.isin(["Yes", "No"]), "No")
        else:
            out["digitized"] = "No"

        # Parse Digitized Date -> python date (NaT stays null).
        if "digitized_date" in out.columns:
            out["digitized_date"] = pd.to_datetime(
                out["digitized_date"], errors="coerce"
            ).dt.date
        else:
            out["digitized_date"] = None

        # A row that isn't digitized has no digitized date.
        out.loc[out["digitized"] != "Yes", "digitized_date"] = None

        if unknown:
            extra_df = raw[unknown].apply(_clean_text_series)
            out["extra"] = extra_df.apply(
                lambda r: json.dumps({k: v for k, v in r.items() if v}), axis=1
            )
        else:
            out["extra"] = ""

        combined.append(out)

    frame = pd.concat(combined, ignore_index=True, sort=False)
    frame = frame.reindex(columns=DATA_COLUMNS)

    # Text columns: fill missing with "" so the DB stays consistently non-null text.
    for col in DATA_COLUMNS:
        if col == "digitized_date":
            continue
        frame[col] = frame[col].fillna("")

    frame["digitized_date"] = frame["digitized_date"].where(
        pd.notna(frame["digitized_date"]), None
    )
    return frame


def import_workbook(source: str | BinaryIO) -> dict[str, int]:
    """Load a workbook and replace the `assets` table. Returns per-media-type counts."""
    frame = load_workbook(source)
    replace_all(frame)
    counts = frame["media_type"].value_counts().to_dict()
    counts["_total"] = int(len(frame))
    return counts
