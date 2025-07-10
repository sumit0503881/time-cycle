# =============================================================
# File: app.py – Time‑Cycle Overlap Visualiser (Experimental)
# Added: table‑only Year/Month filters + CSV download buttons
# Uses st.session_state to keep results on widget change
# Updated: 03‑May‑2025
# =============================================================
from __future__ import annotations
import streamlit as st, pandas as pd, plotly.graph_objects as go
from pathlib import Path
from engine import detect_pivots, project_intervals, load_holiday_calendar

st.set_page_config(page_title="Time‑Cycle Strategy", layout="wide")
st.title("📈 Time‑Cycle Overlap Visualiser (Experimental)")

# ---------------- Sidebar (unchanged inputs) ----------------
with st.sidebar:
    st.header("Upload data & parameters")
    csv_file       = st.file_uploader("Price CSV / XLSX", type=["csv","xlsx"])
    holiday_file   = st.file_uploader("Holiday CSV (optional)", type=["csv"])
    extra_holidays = st.date_input("Add ad‑hoc holidays", [])
    st.subheader("Pivot settings")
    pivot_range = st.number_input("Pivot range (bars)", 1,100,5,1)
    min_move    = st.number_input("Min move (points)", 0.0, value=100.0, step=1.0)
    st.subheader("Interval list")
    iv_text = st.text_input("Comma‑separated intervals", "30,60,90,120,144,180,210,240,270,360")
    iv_list = [int(x.strip()) for x in iv_text.split(",") if x.strip().isdigit()]
    mode     = st.selectbox("Interval unit", ["Bars","Calendar Days"])
    use_bars = mode=="Bars"
    overlap_thr = st.number_input("Highlight threshold (≥ N overlaps)", 1,100,3,1)
    run_btn = st.button("▶️ Run analysis", type="primary")

# ---------------- Helper ----------------

def _read_price_file(upload)->pd.DataFrame:
    suffix = Path(upload.name).suffix.lower()
    df = pd.read_csv(upload) if suffix==".csv" else pd.read_excel(upload)
    df.columns = [c.strip().title() for c in df.columns]
    if df["Date"].astype(str).str.contains(":").any():
        df["Date"] = pd.to_datetime(df["Date"], format="%d-%b-%Y %H:%M")
    else:
        df["Date"] = pd.to_datetime(df["Date"], format="%d-%b-%Y")
    return df.set_index("Date").sort_index()

# ---------------- Run analysis once ----------------
if run_btn:
    if not csv_file:
        st.error("Please upload a price file first."); st.stop()

    price_df = _read_price_file(csv_file)
    is_intraday = price_df.index.astype(str).str.contains(":").any()
    date_fmt    = "%d-%b-%Y %H:%M" if is_intraday else "%d-%b-%Y"

    holiday_set = load_holiday_calendar(uploaded_file_object=holiday_file if holiday_file else None,
                                        adhoc=extra_holidays if extra_holidays else None)

    pivots_df = detect_pivots(price_df, pivot_range=int(pivot_range), min_move=min_move)
    st.success(f"Detected {len(pivots_df)} pivots (H+L)")

    interval_hits = pd.DataFrame(project_intervals(pivots_df, iv_list, use_bars,
                                                   price_df, holiday_set),
                                 columns=["Source Pivot Date","Interval (Days)","Projected Date"])
    overlaps_full  = interval_hits.groupby("Projected Date")
    overlaps_count = overlaps_full.size().to_dict()

    # tables
    piv_view = pivots_df.copy()
    piv_view["Pivot Date"] = piv_view["idx"].dt.strftime(date_fmt)
    piv_view["Year"]  = pivots_df["idx"].dt.year
    piv_view["Month"] = pivots_df["idx"].dt.month
    piv_view = piv_view.rename(columns={"type":"Type","price":"Price","abs_move":"Absolute Movement"})

    rows=[]
    for pdts,grp in overlaps_full:
        if len(grp)<overlap_thr: continue
        rows.append({"Date":pdts.strftime(date_fmt),
                     "Overlap Count":len(grp),
                     "Source Dates":", ".join(grp["Source Pivot Date"].dt.strftime(date_fmt)),
                     "Intervals":", ".join(grp["Interval (Days)"].astype(str)),
                     "Year":pdts.year,"Month":pdts.month})
    ov_view = pd.DataFrame(rows).sort_values("Overlap Count",ascending=False)

    st.session_state["pivots_view"]  = piv_view
    st.session_state["overlaps_view"]= ov_view
    st.session_state["chart_data"]   = (price_df,pivots_df,overlaps_count,overlap_thr)

# ---------------- Display ----------------
if "pivots_view" in st.session_state:
    pivots_view  = st.session_state["pivots_view"]
    overlaps_view= st.session_state["overlaps_view"]
    price_df, pivots_df, overlaps_count, overlap_thr = st.session_state["chart_data"]

    pivot_tab, overlap_tab = st.tabs(["🔺 Pivots","🎯 Overlaps"])

    # ----- Pivot Tab -----
    with pivot_tab:
        st.subheader("Pivot Highs and Lows")
        yr_sel = st.selectbox("Year",  ["All"]+sorted(pivots_view["Year"].unique()),0,key="pv_year")
        mn_sel = st.selectbox("Month", ["All"]+list(range(1,13)),0,key="pv_month",
                              format_func=lambda m: m if m=="All" else f"{m:02d}")
        pv_f = pivots_view.copy()
        if yr_sel!="All": pv_f = pv_f[pv_f["Year"]==yr_sel]
        if mn_sel!="All": pv_f = pv_f[pv_f["Month"]==mn_sel]
        st.dataframe(pv_f.drop(columns=["Year","Month","idx"]), use_container_width=True)
        csv_pivot = pv_f.drop(columns=["Year","Month","idx"]).to_csv(index=False).encode("utf-8")
        st.download_button("Download Pivot Table", csv_pivot, "pivots.csv", "text/csv")

    # ----- Overlap Tab -----
    with overlap_tab:
        st.subheader("Overlap Dates")
        yr2 = st.selectbox("Year",  ["All"]+sorted(overlaps_view["Year"].unique()),0,key="ov_year")
        mn2 = st.selectbox("Month", ["All"]+list(range(1,13)),0,key="ov_month",
                           format_func=lambda m: m if m=="All" else f"{m:02d}")
        ov_f = overlaps_view.copy()
        if yr2!="All": ov_f = ov_f[ov_f["Year"]==yr2]
        if mn2!="All": ov_f = ov_f[ov_f["Month"]==mn2]
        st.dataframe(ov_f.drop(columns=["Year","Month"]), use_container_width=True)
        csv_overlap = ov_f.drop(columns=["Year","Month"]).to_csv(index=False).encode("utf-8")
        st.download_button("Download Overlap Table", csv_overlap, "overlaps.csv", "text/csv")

    # ----- Chart (quick redraw) -----
    fig = go.Figure()
    fig.add_trace(go.Candlestick(x=price_df.index, open=price_df["Open"],high=price_df["High"],
                                 low=price_df["Low"], close=price_df["Close"], name="Price"))
    fig.add_trace(go.Scatter(x=pivots_df.query('type == "H"')["idx"], y=pivots_df.query('type == "H"')["price"],
                             mode="markers", marker=dict(symbol="triangle-up",size=9,color="red"), name="Pivot High"))
    fig.add_trace(go.Scatter(x=pivots_df.query('type == "L"')["idx"], y=pivots_df.query('type == "L"')["price"],
                             mode="markers", marker=dict(symbol="triangle-down",size=9,color="green"), name="Pivot Low"))
    for dt,cnt in overlaps_count.items():
        if cnt>=overlap_thr:
            fig.add_shape(type="line",x0=dt,x1=dt,y0=price_df["Low"].min(),y1=price_df["High"].max(),
                          line=dict(color="purple",dash="dot"))
    fig.update_layout(height=650,xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)
