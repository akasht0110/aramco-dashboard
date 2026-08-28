"""Admin-only: replace the database contents from an uploaded Excel workbook."""

import streamlit as st

from lib import db
from lib.auth import current_user
from lib.ingest import import_workbook

user = current_user()
if not user["is_admin"]:
    st.error("You do not have access to this page.")
    st.stop()

st.title("Data Import")
st.write(
    "Upload the source Excel workbook to refresh the dashboard database. "
    "This **replaces all existing data** — one sheet per category, every "
    "column read as text, `Digitized Date` parsed as a date."
)

current = db.overall_totals()
st.caption(
    f"Currently loaded: {current['total']:,} assets "
    f"({current['digitized']:,} digitized)."
)

uploaded = st.file_uploader("Excel workbook (.xlsx)", type=["xlsx"])

if uploaded is not None:
    st.write(f"Selected: **{uploaded.name}** ({uploaded.size / 1_048_576:.1f} MB)")
    if st.button("Import and replace database", type="primary"):
        with st.spinner("Reading workbook and loading database…"):
            try:
                counts = import_workbook(uploaded)
            except Exception as exc:  # surface parse/DB errors to the admin
                st.exception(exc)
                st.stop()

        st.cache_data.clear()
        total = counts.pop("_total")
        st.success(f"Imported {total:,} assets.")
        st.table(
            {"Category": list(counts.keys()), "Rows": list(counts.values())}
        )

st.divider()
st.markdown(
    "**Large files (hundreds of thousands of rows or more)** are better loaded "
    "from the command line, which avoids the browser upload limit:\n\n"
    "```\n"
    "python import_data.py \"URL Dashboard Database Testing.xlsx\"\n"
    "```\n"
    "Set the `DATABASE_URL` environment variable first to target the production database."
)
