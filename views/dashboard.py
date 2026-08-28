"""Home page: digitization progress across all media types, with growth trends."""

import datetime as dt

import plotly.express as px
import streamlit as st

from lib import db, metrics

st.title("Dashboard")
st.caption("Digitization progress across all categories")

totals = db.overall_totals()

if totals["total"] == 0:
    st.warning(
        "No data loaded yet. An administrator can load the workbook from the "
        "**Data Import** page."
    )
    st.stop()

# --- top-line KPIs --------------------------------------------------------
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Assets", f"{totals['total']:,}")
c2.metric("Digitized", f"{totals['digitized']:,}")
c3.metric("Remaining", f"{totals['remaining']:,}")
c4.metric("% Complete", f"{totals['pct_complete']:.1f}%")

st.progress(min(totals["pct_complete"] / 100, 1.0))

# --- growth --------------------------------------------------------------
ts = db.digitized_timeseries()
today = dt.date.today()
latest = db.latest_activity_date()

# Anchor the rolling windows to the most recent activity so the metrics stay
# meaningful even if the database has not been refreshed for a few days. With
# daily updates in production this equals today.
anchor = min(today, latest) if latest else today

wow = metrics.window_growth(ts, anchor, 7)
mom = metrics.window_growth(ts, anchor, 30)

st.subheader("Growth")
g1, g2 = st.columns(2)


def _fmt_delta(g: dict) -> str | None:
    if g["previous"] == 0 and g["current"] == 0:
        return None
    if g["pct"] is None:
        return f"{g['delta']:+,} vs prev"
    return f"{g['delta']:+,} ({g['pct']:+.0f}%) vs prev period"


g1.metric(
    "Week on Week", f"{wow['current']:,}", _fmt_delta(wow),
    help=f"Assets digitized in the 7 days ending {anchor:%d %b %Y}, vs the 7 days before.",
)
g2.metric(
    "Month on Month", f"{mom['current']:,}", _fmt_delta(mom),
    help=f"Assets digitized in the 30 days ending {anchor:%d %b %Y}, vs the 30 days before.",
)

if latest:
    note = f"Windows anchored to the most recent digitization activity: **{latest:%d %b %Y}**"
    if latest < today - dt.timedelta(days=3):
        note += "  ·  database may be due a refresh"
    st.caption(note)

st.divider()

# --- charts ------------------------------------------------------------
left, right = st.columns(2)

cum = metrics.cumulative_series(ts)
if not cum.empty:
    fig = px.area(
        cum, x="date", y="cumulative",
        title="Cumulative digitized assets over time",
        labels={"date": "", "cumulative": "Digitized (running total)"},
    )
    fig.update_traces(line_color="#0072C6", fillcolor="rgba(0,114,198,0.15)")
    left.plotly_chart(fig, use_container_width=True)

wk = metrics.weekly_series(ts)
if not wk.empty:
    fig = px.bar(
        wk, x="week_start", y="count",
        title="Digitized per week",
        labels={"week_start": "Week starting", "count": "Assets"},
    )
    fig.update_traces(marker_color="#0072C6")
    right.plotly_chart(fig, use_container_width=True)

by_type = db.totals_by_media_type()

fig = px.bar(
    by_type, x="media_type", y="pct_complete",
    title="% complete by category", text="pct_complete",
    labels={"media_type": "", "pct_complete": "% complete"},
    range_y=[0, 100],
)
fig.update_traces(marker_color="#0072C6", texttemplate="%{text:.1f}%")
left.plotly_chart(fig, use_container_width=True)

stacked = by_type.melt(
    id_vars="media_type",
    value_vars=["digitized", "remaining"],
    var_name="status",
    value_name="count",
)
fig = px.bar(
    stacked, x="media_type", y="count", color="status",
    title="Digitized vs remaining by category",
    labels={"media_type": "", "count": "Assets", "status": ""},
    color_discrete_map={"digitized": "#0072C6", "remaining": "#D0D7DE"},
)
right.plotly_chart(fig, use_container_width=True)

st.divider()
st.subheader("By category")
st.dataframe(
    by_type.rename(
        columns={
            "media_type": "Category",
            "total": "Total",
            "digitized": "Digitized",
            "remaining": "Remaining",
            "pct_complete": "% Complete",
        }
    ),
    hide_index=True,
    use_container_width=True,
)
