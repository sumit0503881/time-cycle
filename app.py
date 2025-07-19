# =============================================================
# File: app.py – Time‑Cycle Overlap Visualiser (Experimental)
# Added: Triangle-based pivot filtering
# Updated: December 2024
# =============================================================
from __future__ import annotations
import streamlit as st, pandas as pd, plotly.graph_objects as go
from pathlib import Path
import os
from engine import (
    detect_pivots,
    project_intervals,
    load_holiday_calendar,
    setup_debugger,
    log_exceptions,
)
from engine.triangle import filter_pivots_by_triangle

if os.getenv("DEBUG", "0") == "1":
    setup_debugger()

st.set_page_config(page_title="Time‑Cycle Strategy", layout="wide")
st.title("📈 Time‑Cycle Overlap Visualiser (Experimental)")

# ---------------- Sidebar ----------------
with st.sidebar:
    st.header("Upload data & parameters")
    csv_file       = st.file_uploader("Price CSV / XLSX", type=["csv","xlsx"])
    holiday_file   = st.file_uploader("Holiday CSV (optional)", type=["csv"])
    extra_holidays = st.date_input("Add ad‑hoc holidays", [])
    
    st.subheader("Pivot settings")
    pivot_range = st.number_input("Pivot range (bars)", 1,100,5,1)
    min_move    = st.number_input("Min move (points)", 0.0, value=100.0, step=1.0)
    
    # Triangle Filter Settings
    st.subheader("Triangle Filter Settings")
    enable_triangle = st.checkbox("Enable Triangle Filter", value=False)
    triangle_settings = {"enabled": enable_triangle}
    
    if enable_triangle:
        triangle_types = st.multiselect(
            "Triangle Types",
            ["equilateral", "isosceles", "scalene"],
            default=["equilateral", "isosceles"]
        )
        triangle_settings["types"] = triangle_types
        
        time_scale = st.slider(
            "Time Scale Factor", 
            min_value=1, 
            max_value=50, 
            value=10,
            help="Converts 1 day to N price units for distance calculation"
        )
        triangle_settings["time_scale"] = time_scale
        
        tolerance = st.slider(
            "Shape Tolerance %", 
            min_value=0, 
            max_value=50, 
            value=10,
            help="Maximum % difference for shape matching"
        )
        triangle_settings["tolerance"] = tolerance
        
        min_symmetry = st.slider(
            "Minimum Symmetry Score %",
            min_value=0,
            max_value=100,
            value=70,
            help="Filter triangles by symmetry score"
        )
        triangle_settings["min_symmetry"] = min_symmetry
        
        show_triangles = st.checkbox("Show Triangle Overlays", value=True)
        triangle_settings["show_overlays"] = show_triangles
        triangle_settings["pivot_range"] = pivot_range
    
    st.subheader("Interval list")
    iv_text = st.text_input("Comma‑separated intervals", "30,60,90,120,144,180,210,240,270,360")
    iv_list = [int(x.strip()) for x in iv_text.split(",") if x.strip().isdigit()]
    mode     = st.selectbox("Interval unit", ["Bars","Calendar Days"])
    use_bars = mode=="Bars"
    overlap_thr = st.number_input("Highlight threshold (≥ N overlaps)", 1,100,3,1)
    run_btn = st.button("▶️ Run analysis", type="primary")

# ---------------- Helper ----------------

@log_exceptions
def _read_price_file(upload) -> pd.DataFrame:
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

    # Detect all pivots first
    all_pivots_df = detect_pivots(price_df, pivot_range=int(pivot_range), min_move=min_move)
    
    # Apply triangle filter if enabled
    pivots_df = filter_pivots_by_triangle(price_df, all_pivots_df, triangle_settings)
    
    if enable_triangle:
        st.success(f"Detected {len(all_pivots_df)} pivots total, {len(pivots_df)} after triangle filter")
    else:
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
    
    # Add triangle info if available
    if "triangle_type" in pivots_df.columns:
        piv_view["Triangle Type"] = pivots_df["triangle_type"]
        piv_view["Symmetry Score"] = pivots_df["symmetry_score"].round(1)

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
    st.session_state["chart_data"]   = (price_df,pivots_df,overlaps_count,overlap_thr,triangle_settings)

# ---------------- Display ----------------
if "pivots_view" in st.session_state:
    pivots_view  = st.session_state["pivots_view"]
    overlaps_view= st.session_state["overlaps_view"]
    price_df, pivots_df, overlaps_count, overlap_thr, triangle_settings = st.session_state["chart_data"]

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
        
        # Select columns to display
        display_cols = ["Pivot Date", "Type", "Price", "Absolute Movement"]
        if "Triangle Type" in pv_f.columns:
            display_cols.extend(["Triangle Type", "Symmetry Score"])
        
        st.dataframe(pv_f[display_cols], use_container_width=True)
        csv_pivot = pv_f[display_cols].to_csv(index=False).encode("utf-8")
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

    # ----- Chart (with triangle overlays) -----
    fig = go.Figure()
    fig.add_trace(go.Candlestick(x=price_df.index, open=price_df["Open"],high=price_df["High"],
                                 low=price_df["Low"], close=price_df["Close"], name="Price"))
    
    # Plot pivots
    high_pivots = pivots_df.query('type == "H"')
    low_pivots = pivots_df.query('type == "L"')
    
    fig.add_trace(go.Scatter(x=high_pivots["idx"], y=high_pivots["price"],
                             mode="markers", marker=dict(symbol="triangle-up",size=9,color="red"), 
                             name="Pivot High"))
    fig.add_trace(go.Scatter(x=low_pivots["idx"], y=low_pivots["price"],
                             mode="markers", marker=dict(symbol="triangle-down",size=9,color="green"), 
                             name="Pivot Low"))
    
    # Draw triangle overlays if enabled
    if triangle_settings.get("enabled", False) and triangle_settings.get("show_overlays", False):
        for _, pivot in high_pivots.iterrows():
            if "triangle_info" in pivot and pd.notna(pivot.get("triangle_info")):
                info = pivot["triangle_info"]
                # Draw triangle lines
                fig.add_trace(go.Scatter(
                    x=[info["left_base_idx"], pivot["idx"], info["right_base_idx"], info["left_base_idx"]],
                    y=[info["left_base_price"], pivot["price"], info["right_base_price"], info["left_base_price"]],
                    mode="lines",
                    line=dict(color="orange", width=1, dash="dot"),
                    showlegend=False,
                    hoverinfo="skip"
                ))
    
    # Overlap lines
    for dt,cnt in overlaps_count.items():
        if cnt>=overlap_thr:
            fig.add_shape(type="line",x0=dt,x1=dt,y0=price_df["Low"].min(),y1=price_df["High"].max(),
                          line=dict(color="purple",dash="dot"))
    
    fig.update_layout(height=650,xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)
