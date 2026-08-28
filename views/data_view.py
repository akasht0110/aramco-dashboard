"""Data View: pick a category, filter on any column, browse and export."""

import datetime as dt

import streamlit as st

from lib import db

st.title("Data View")

categories = db.media_types()
if not categories:
    st.warning(
        "No data loaded yet. An administrator can load the workbook from the "
        "**Data Import** page."
    )
    st.stop()

media_type = st.selectbox("Category", categories)

# --- filters -----------------------------------------------------------
filters: dict = {"media_type": media_type, "multi": {}, "text": {}}

with st.expander("Filters", expanded=False):
    # Free-text "contains" search.
    tcols = st.columns(len(db.TEXT_SEARCH_COLUMNS))
    for col, holder in zip(db.TEXT_SEARCH_COLUMNS, tcols):
        term = holder.text_input(
            db.COLUMN_LABELS.get(col, col), key=f"txt_{media_type}_{col}"
        )
        if term.strip():
            filters["text"][col] = term.strip()

    # Categorical multiselects (only shown when the column has values).
    cat_cols = [
        c
        for c in db.CATEGORICAL_COLUMNS
        if c != "digitized" and db.distinct_values(c, media_type)
    ]
    grid = st.columns(3)
    for i, col in enumerate(cat_cols):
        opts = db.distinct_values(col, media_type)
        chosen = grid[i % 3].multiselect(
            db.COLUMN_LABELS.get(col, col), opts, key=f"ms_{media_type}_{col}"
        )
        if chosen:
            filters["multi"][col] = chosen

    d1, d2, d3 = st.columns(3)
    dig_choice = d1.multiselect(
        "Digitized", ["Yes", "No"], key=f"dig_{media_type}"
    )
    if dig_choice:
        filters["multi"]["digitized"] = dig_choice

    date_from = d2.date_input(
        "Digitized from", value=None, key=f"df_{media_type}", format="YYYY-MM-DD"
    )
    date_to = d3.date_input(
        "Digitized to", value=None, key=f"dt_{media_type}", format="YYYY-MM-DD"
    )
    if isinstance(date_from, dt.date):
        filters["date_from"] = date_from
    if isinstance(date_to, dt.date):
        filters["date_to"] = date_to

# --- results ---------------------------------------------------------
total = db.count_assets(filters)
st.subheader(f"{total:,} records")

if total == 0:
    st.info("No records match the current filters.")
    st.stop()

pc1, pc2 = st.columns([1, 3])
page_size = pc1.selectbox("Rows per page", [50, 100, 200, 500], index=1)
n_pages = (total + page_size - 1) // page_size
page = pc2.number_input(
    f"Page (1–{n_pages})", min_value=1, max_value=n_pages, value=1, step=1
)

df = db.query_assets(filters, limit=page_size, offset=(page - 1) * page_size)
df = df.rename(columns={c: db.COLUMN_LABELS.get(c, c) for c in df.columns})
st.dataframe(df, hide_index=True, use_container_width=True)

# --- export ---------------------------------------------------------
EXPORT_CAP = 50_000
if total <= EXPORT_CAP:
    full = db.query_assets(filters)
    full = full.rename(columns={c: db.COLUMN_LABELS.get(c, c) for c in full.columns})
    st.download_button(
        f"Download all {total:,} filtered rows (CSV)",
        data=full.to_csv(index=False).encode("utf-8"),
        file_name=f"{media_type.replace(' ', '_').lower()}_filtered.csv",
        mime="text/csv",
    )
else:
    st.caption(
        f"Add more filters to bring the result under {EXPORT_CAP:,} rows to enable CSV export."
    )
