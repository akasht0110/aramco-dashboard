"""
Growth metrics derived from the `digitized_date` column.

`window_growth` compares a trailing window (e.g. last 7 days) against the
immediately preceding window of the same length. `weekly_series` and
`cumulative_series` feed the dashboard charts.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd


def _as_datetime(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    return df


def window_growth(
    timeseries: pd.DataFrame, anchor: dt.date, days: int
) -> dict:
    """
    timeseries: columns [date, count] (one row per day, digitized count).
    Returns current-window total, previous-window total, and the delta.
    """
    anchor = pd.Timestamp(anchor)
    cur_start = anchor - pd.Timedelta(days=days)
    prev_start = anchor - pd.Timedelta(days=2 * days)

    if timeseries.empty:
        return {"current": 0, "previous": 0, "delta": 0, "pct": None}

    ts = _as_datetime(timeseries)
    cur = int(ts.loc[(ts["date"] > cur_start) & (ts["date"] <= anchor), "count"].sum())
    prev = int(
        ts.loc[(ts["date"] > prev_start) & (ts["date"] <= cur_start), "count"].sum()
    )
    delta = cur - prev
    pct = (delta / prev * 100) if prev else None
    return {"current": cur, "previous": prev, "delta": delta, "pct": pct}


def weekly_series(timeseries: pd.DataFrame) -> pd.DataFrame:
    """Digitized count per ISO week (week start Monday). Columns [week_start, count]."""
    if timeseries.empty:
        return pd.DataFrame(columns=["week_start", "count"])
    ts = _as_datetime(timeseries)
    ts["week_start"] = ts["date"] - pd.to_timedelta(ts["date"].dt.weekday, unit="D")
    out = (
        ts.groupby("week_start", as_index=False)["count"]
        .sum()
        .sort_values("week_start")
    )
    return out


def monthly_series(timeseries: pd.DataFrame) -> pd.DataFrame:
    """Digitized count per calendar month. Columns [month, count]."""
    if timeseries.empty:
        return pd.DataFrame(columns=["month", "count"])
    ts = _as_datetime(timeseries)
    ts["month"] = ts["date"].dt.to_period("M").dt.to_timestamp()
    out = ts.groupby("month", as_index=False)["count"].sum().sort_values("month")
    return out


def cumulative_series(timeseries: pd.DataFrame) -> pd.DataFrame:
    """Running total of digitized assets over time. Columns [date, cumulative]."""
    if timeseries.empty:
        return pd.DataFrame(columns=["date", "cumulative"])
    ts = _as_datetime(timeseries).sort_values("date")
    ts["cumulative"] = ts["count"].cumsum()
    return ts[["date", "cumulative"]]
