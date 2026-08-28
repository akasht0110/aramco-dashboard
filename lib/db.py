"""
Database layer: SQLAlchemy engine, the `assets` table schema, and cached
read helpers. All filtering and aggregation happens in SQL so the app never
pulls the whole table (potentially ~2M rows) into memory.
"""

from __future__ import annotations

import datetime as dt
from functools import lru_cache

import pandas as pd
from sqlalchemy import (
    Date,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Column,
    case,
    create_engine,
    delete,
    distinct,
    func,
    select,
)
from sqlalchemy.engine import Engine

from lib.config import database_url

metadata = MetaData()

# Human-readable Excel header -> database column. Any header not in this map is
# preserved as JSON text in the `extra` column so a new sheet layout in the
# future does not break ingestion.
COLUMN_MAP: dict[str, str] = {
    "Type": "type",
    "Category": "category",
    "Accession ID": "accession_id",
    "Building": "building",
    "Vault": "vault",
    "Rack": "rack",
    "Shelf": "shelf",
    "Asset ID": "asset_id",
    "Title": "title",
    "Sub-Type": "sub_type",
    "Year": "year",
    "Size": "size",
    "Color": "color",
    "Digitized": "digitized",
    "Digitized Date": "digitized_date",
    "Billing": "billing",
    "Billing Number": "billing_number",
}

# Nice labels for the UI (reverse of COLUMN_MAP, plus media_type).
COLUMN_LABELS: dict[str, str] = {"media_type": "Media Type"}
COLUMN_LABELS.update({v: k for k, v in COLUMN_MAP.items()})

# Columns offered as free-text "contains" search in Data View.
TEXT_SEARCH_COLUMNS = ["title", "asset_id", "accession_id"]

# Columns offered as multiselect (value pick-list) filters in Data View.
CATEGORICAL_COLUMNS = [
    "type",
    "building",
    "vault",
    "rack",
    "shelf",
    "sub_type",
    "year",
    "color",
    "digitized",
    "billing",
    "billing_number",
]

# Order columns are shown in the Data View table.
DISPLAY_ORDER = [
    "media_type",
    "type",
    "category",
    "accession_id",
    "asset_id",
    "title",
    "sub_type",
    "building",
    "vault",
    "rack",
    "shelf",
    "year",
    "size",
    "color",
    "digitized",
    "digitized_date",
    "billing",
    "billing_number",
]

assets = Table(
    "assets",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("media_type", String, nullable=False),
    Column("type", String),
    Column("category", String),
    Column("accession_id", String),
    Column("building", String),
    Column("vault", String),
    Column("rack", String),
    Column("shelf", String),
    Column("asset_id", String),
    Column("title", String),
    Column("sub_type", String),
    Column("year", String),
    Column("size", String),
    Column("color", String),
    Column("digitized", String),
    Column("digitized_date", Date),
    Column("billing", String),
    Column("billing_number", String),
    Column("extra", String),
    Index("ix_assets_media_type", "media_type"),
    Index("ix_assets_digitized", "digitized"),
    Index("ix_assets_digitized_date", "digitized_date"),
    Index("ix_assets_building", "building"),
)

DATA_COLUMNS = [c.name for c in assets.columns if c.name != "id"]


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    url = database_url()
    kwargs: dict = {"pool_pre_ping": True, "future": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    engine = create_engine(url, **kwargs)
    metadata.create_all(engine)
    return engine


# --- caching shim: works with or without a Streamlit runtime -----------------
def _cache_data(ttl: int = 60):
    try:
        import streamlit as st
        from streamlit.runtime import exists as _runtime_exists

        if _runtime_exists():
            return st.cache_data(ttl=ttl, show_spinner=False)
    except Exception:
        pass

    def passthrough(fn):
        return fn

    return passthrough


# --- filter helpers ---------------------------------------------------------
def _apply_filters(stmt, filters: dict):
    """
    filters shape:
      {
        "media_type": "Magnetic Tapes" | None,
        "multi": {"building": ["MPD", ...], ...},
        "text": {"title": "pharmacy", ...},
        "date_from": date | None,
        "date_to": date | None,
      }
    """
    media_type = filters.get("media_type")
    if media_type:
        stmt = stmt.where(assets.c.media_type == media_type)

    for col, values in (filters.get("multi") or {}).items():
        if values:
            stmt = stmt.where(assets.c[col].in_(list(values)))

    for col, term in (filters.get("text") or {}).items():
        if term:
            stmt = stmt.where(assets.c[col].ilike(f"%{term}%"))

    if filters.get("date_from"):
        stmt = stmt.where(assets.c.digitized_date >= filters["date_from"])
    if filters.get("date_to"):
        stmt = stmt.where(assets.c.digitized_date <= filters["date_to"])

    return stmt


# --- read helpers ---------------------------------------------------------
@_cache_data(ttl=60)
def overall_totals() -> dict:
    eng = get_engine()
    with eng.connect() as conn:
        total = conn.execute(select(func.count()).select_from(assets)).scalar_one()
        digitized = conn.execute(
            select(func.count()).select_from(assets).where(assets.c.digitized == "Yes")
        ).scalar_one()
    remaining = total - digitized
    pct = (digitized / total * 100) if total else 0.0
    return {
        "total": total,
        "digitized": digitized,
        "remaining": remaining,
        "pct_complete": pct,
    }


@_cache_data(ttl=60)
def totals_by_media_type() -> pd.DataFrame:
    eng = get_engine()
    stmt = select(
        assets.c.media_type.label("media_type"),
        func.count().label("total"),
        func.sum(
            case((assets.c.digitized == "Yes", 1), else_=0)
        ).label("digitized"),
    ).group_by(assets.c.media_type).order_by(assets.c.media_type)
    with eng.connect() as conn:
        df = pd.read_sql(stmt, conn)
    df["digitized"] = df["digitized"].fillna(0).astype(int)
    df["remaining"] = df["total"] - df["digitized"]
    df["pct_complete"] = (df["digitized"] / df["total"] * 100).round(1)
    return df


@_cache_data(ttl=60)
def digitized_timeseries(media_type: str | None = None) -> pd.DataFrame:
    """One row per day that has at least one digitized asset."""
    eng = get_engine()
    stmt = (
        select(
            assets.c.digitized_date.label("date"),
            func.count().label("count"),
        )
        .where(assets.c.digitized == "Yes")
        .where(assets.c.digitized_date.is_not(None))
        .group_by(assets.c.digitized_date)
        .order_by(assets.c.digitized_date)
    )
    if media_type:
        stmt = stmt.where(assets.c.media_type == media_type)
    with eng.connect() as conn:
        df = pd.read_sql(stmt, conn)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
    return df


@_cache_data(ttl=60)
def media_types() -> list[str]:
    eng = get_engine()
    with eng.connect() as conn:
        rows = conn.execute(
            select(distinct(assets.c.media_type)).order_by(assets.c.media_type)
        ).scalars()
        return [r for r in rows if r]


@_cache_data(ttl=60)
def distinct_values(column: str, media_type: str | None = None) -> list[str]:
    eng = get_engine()
    stmt = select(distinct(assets.c[column])).order_by(assets.c[column])
    if media_type:
        stmt = stmt.where(assets.c.media_type == media_type)
    with eng.connect() as conn:
        rows = conn.execute(stmt).scalars()
    return [str(r) for r in rows if r is not None and str(r) != ""]


def count_assets(filters: dict) -> int:
    eng = get_engine()
    stmt = _apply_filters(select(func.count()).select_from(assets), filters)
    with eng.connect() as conn:
        return conn.execute(stmt).scalar_one()


def query_assets(
    filters: dict, limit: int | None = None, offset: int = 0
) -> pd.DataFrame:
    eng = get_engine()
    cols = [assets.c[c] for c in DISPLAY_ORDER if c in assets.c]
    stmt = _apply_filters(select(*cols), filters).order_by(assets.c.id)
    if limit is not None:
        stmt = stmt.limit(limit).offset(offset)
    with eng.connect() as conn:
        return pd.read_sql(stmt, conn)


def replace_all(frame: pd.DataFrame) -> None:
    """Wipe `assets` and reload from a single combined dataframe, in one transaction."""
    eng = get_engine()
    frame = frame.reindex(columns=DATA_COLUMNS)
    is_pg = eng.url.get_backend_name().startswith("postgres")
    # Postgres: big multi-row INSERTs. SQLite: default executemany (its bound
    # parameter cap makes large multi-row INSERTs unsafe).
    to_sql_kwargs = (
        {"chunksize": 10000, "method": "multi"} if is_pg else {"chunksize": 1000}
    )
    with eng.begin() as conn:
        conn.execute(delete(assets))
        frame.to_sql(
            "assets", conn, if_exists="append", index=False, **to_sql_kwargs
        )


def latest_activity_date() -> dt.date | None:
    eng = get_engine()
    with eng.connect() as conn:
        return conn.execute(
            select(func.max(assets.c.digitized_date))
        ).scalar_one_or_none()
