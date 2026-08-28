"""
Aramco Asset Digitization Dashboard — entry point.

Handles authentication, then routes to the multipage app:
  - Dashboard   (home: combined summary + week/month growth)
  - Data View   (per-category table with per-column filters)
  - Data Import (admin only: refresh the database from an Excel workbook)

Run locally:   streamlit run app.py
"""

import streamlit as st

from lib.auth import require_login

st.set_page_config(page_title="Asset Digitization Dashboard", layout="wide")

user = require_login()

with st.sidebar:
    st.markdown(f"**{user['name']}**")
    st.caption("Administrator" if user["is_admin"] else "Viewer")
    user["authenticator"].logout("Log out", location="sidebar")
    st.divider()

pages = [
    st.Page("views/dashboard.py", title="Dashboard", icon=":material/dashboard:", default=True),
    st.Page("views/data_view.py", title="Data View", icon=":material/table_rows:"),
]
if user["is_admin"]:
    pages.append(
        st.Page("views/admin_upload.py", title="Data Import", icon=":material/upload:")
    )

st.navigation(pages).run()
