# =============================================================
# File: app.py – Time‑Cycle Overlap Visualiser (Final Unified Version)
# Description: Combines v10–v14 with triangle filter, revised backtesting,
#              overlap filtering, session state upgrades, and fixed tab logic
# Last Updated: July 2025
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
    analyze_all_projections,
    generate_insights,
    filter_by_overlap_count,
    analyze_overlap_accuracy,
)
from engine.triangle import filter_pivots_by_triangle

if os.getenv("DEBUG", "0") == "1":
    setup_debugger()

st.set_page_config(page_title="Time‑Cycle Strategy", layout="wide")
st.title("📈 Time‑Cycle Overlap Visualiser (Unified)")

# ---------------- Sidebar ----------------
with st.sidebar:
    st.header("Upload data & parameters")
    csv_file       = st.file_uploader("Price CSV / XLSX", type=["csv","xlsx"])
    holiday_file   = st.file_uploader("Holiday CSV (optional)", type=["csv"])
    extra_holidays = st.date_input("Add ad‑hoc holidays", [])

    st.subheader("Pivot settings")
    pivot_range = st.number_input("Pivot range (bars)", 1,100,5,1)
    min_move    = st.number_input("Min move (points)", 0.0, value=100.0, step=1.0)

    st.subheader("Triangle Filter Settings")
    enable_triangle = st.checkbox("Enable Triangle Filter", value=False)
    triangle_settings = {"enabled": enable_triangle}

    if enable_triangle:
        triangle_settings.update({
            "types": st.multiselect("Triangle Types", ["equilateral", "isosceles", "scalene"], default=["equilateral", "isosceles"]),
            "time_scale": st.slider("Time Scale Factor", 1, 50, 10),
            "tolerance": st.slider("Shape Tolerance %", 0, 50, 10),
            "min_symmetry": st.slider("Minimum Symmetry Score %", 0, 100, 70),
            "show_overlays": st.checkbox("Show Triangle Overlays", value=True),
            "pivot_range": pivot_range
        })

    st.subheader("Interval list")
    iv_text = st.text_input("Comma‑separated intervals", "30,60,90,120,144,180,210,240,270,360")
    iv_list = [int(x.strip()) for x in iv_text.split(",") if x.strip().isdigit()]
    use_bars = st.selectbox("Interval unit", ["Bars","Calendar Days"]) == "Bars"
    overlap_thr = st.number_input("Highlight threshold (≥ N overlaps)", 1,100,3,1)

    st.subheader("Backtesting Settings")
    enable_backtesting = st.checkbox("Enable Backtesting", value=False)

    if enable_backtesting:
        lookback_candles = st.number_input("Trend lookback (candles)", 3, 20, 5)
        tolerance_window = st.number_input("Reversal tolerance (candles)", 1, 10, 3)
        min_success_candles = st.number_input("Success criteria (candles)", 1, 5, 1)
        min_overlap_filter = st.number_input("Minimum overlaps filter", 0, 100, 0)

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

# ---------------- Run analysis ----------------

if run_btn:
    if not csv_file:
        st.error("Please upload a price file first."); st.stop()

    price_df = _read_price_file(csv_file)
    is_intraday = price_df.index.astype(str).str.contains(":").any()
    date_fmt    = "%d-%b-%Y %H:%M" if is_intraday else "%d-%b-%Y"

    holiday_set = load_holiday_calendar(uploaded_file_object=holiday_file,
                                        adhoc=extra_holidays)

    all_pivots_df = detect_pivots(price_df, pivot_range=int(pivot_range), min_move=min_move)
    pivots_df = filter_pivots_by_triangle(price_df, all_pivots_df, triangle_settings)

    st.success(f"Detected {len(all_pivots_df)} pivots total, {len(pivots_df)} after triangle filter" if enable_triangle else f"Detected {len(pivots_df)} pivots (H+L)")

    interval_hits = pd.DataFrame(project_intervals(pivots_df, iv_list, use_bars, price_df, holiday_set),
                                 columns=["Source Pivot Date","Interval (Days)","Projected Date"])
    overlaps_full  = interval_hits.groupby("Projected Date")
    overlaps_count = overlaps_full.size().to_dict()

    backtest_results, interval_analysis, overlap_analysis, insights = None, None, None, []

    if enable_backtesting:
        projections = [(r["Source Pivot Date"], r["Interval (Days)"], r["Projected Date"]) for _, r in interval_hits.iterrows()]
        filtered_projections = filter_by_overlap_count(projections, overlaps_count, min_overlap_filter) if min_overlap_filter > 0 else projections
        if min_overlap_filter > 0:
            st.info(f"Analyzing {len(filtered_projections)} projections with {min_overlap_filter}+ overlaps (out of {len(projections)} total)")

        if filtered_projections:
            validation_results, interval_stats = analyze_all_projections(
                filtered_projections, price_df, tolerance_window, min_success_candles, lookback_candles)
            insights = generate_insights(interval_stats, validation_results)
            interval_analysis = pd.DataFrame([
                {
                    "Interval": i,
                    "Total Projections": s['total_count'],
                    "Successful": s['success_count'],
                    "Success Rate %": f"{s['success_rate']:.1f}",
                    "Immediate Reversals": s['immediate_reversals'],
                    "Immediate %": f"{s['immediate_reversal_rate']:.1f}",
                    "Avg Candles to Reversal": f"{s['avg_candles_to_reversal']:.1f}"
                } for i, s in sorted(interval_stats.items()) if s['total_count'] > 0
            ])
            overlap_analysis = analyze_overlap_accuracy(validation_results, overlaps_count)
            backtest_results = pd.DataFrame(validation_results)
        else:
            st.warning(f"No projections found with {min_overlap_filter}+ overlaps")

    piv_view = pivots_df.copy()
    piv_view["Pivot Date"] = piv_view["idx"].dt.strftime(date_fmt)
    piv_view["Year"] = pivots_df["idx"].dt.year
    piv_view["Month"] = pivots_df["idx"].dt.month
    piv_view = piv_view.rename(columns={"type":"Type","price":"Price","abs_move":"Absolute Movement"})
    if "triangle_type" in pivots_df.columns:
        piv_view["Triangle Type"] = pivots_df["triangle_type"]
        piv_view["Symmetry Score"] = pivots_df["symmetry_score"].round(1)

    ov_view = pd.DataFrame([
        {"Date": d.strftime(date_fmt), "Overlap Count": len(g),
         "Source Dates": ", ".join(g["Source Pivot Date"].dt.strftime(date_fmt)),
         "Intervals": ", ".join(g["Interval (Days)"].astype(str)),
         "Year": d.year, "Month": d.month}
        for d, g in overlaps_full if len(g) >= overlap_thr
    ]).sort_values("Overlap Count", ascending=False)

    st.session_state["pivots_view"] = piv_view
    st.session_state["overlaps_view"] = ov_view
    st.session_state["chart_data"] = (price_df, pivots_df, overlaps_count, overlap_thr, triangle_settings)
    st.session_state["backtest_results"] = (backtest_results, interval_analysis, overlap_analysis, insights, enable_backtesting)

# ---------------- Display ----------------

if "pivots_view" in st.session_state:
    pivots_view = st.session_state["pivots_view"]
    overlaps_view = st.session_state["overlaps_view"]
    price_df, pivots_df, overlaps_count, overlap_thr, triangle_settings = st.session_state["chart_data"]

    tabs = ["\ud83d\udd3a Pivots", "\ud83c\udfaf Overlaps"]
    if len(st.session_state.get("backtest_results", [])) == 5 and st.session_state["backtest_results"][4]:
        tabs.append("\ud83d\udcca Backtesting")

    tab_objs = st.tabs(tabs)
    pivot_tab, overlap_tab = tab_objs[0], tab_objs[1]
    backtest_tab = tab_objs[2] if len(tab_objs) == 3 else None

    with pivot_tab:
        st.subheader("Pivot Highs and Lows")
        yr_sel = st.selectbox("Year",  ["All"] + sorted(pivots_view["Year"].unique()), 0, key="pv_year")
        mn_sel = st.selectbox("Month", ["All"] + list(range(1,13)), 0, key="pv_month", format_func=lambda m: m if m=="All" else f"{m:02d}")
        pv_f = pivots_view.copy()
        if yr_sel != "All": pv_f = pv_f[pv_f["Year"] == yr_sel]
        if mn_sel != "All": pv_f = pv_f[pv_f["Month"] == mn_sel]
        cols = ["Pivot Date", "Type", "Price", "Absolute Movement"] + [c for c in ["Triangle Type", "Symmetry Score"] if c in pv_f.columns]
        st.dataframe(pv_f[cols], use_container_width=True)
        st.download_button("Download Pivot Table", pv_f[cols].to_csv(index=False).encode("utf-8"), "pivots.csv")

    with overlap_tab:
        st.subheader("Overlap Dates")
        yr2 = st.selectbox("Year",  ["All"] + sorted(overlaps_view["Year"].unique()), 0, key="ov_year")
        mn2 = st.selectbox("Month", ["All"] + list(range(1,13)), 0, key="ov_month", format_func=lambda m: m if m=="All" else f"{m:02d}")
        ov_f = overlaps_view.copy()
        if yr2 != "All": ov_f = ov_f[ov_f["Year"] == yr2]
        if mn2 != "All": ov_f = ov_f[ov_f["Month"] == mn2]
        st.dataframe(ov_f.drop(columns=["Year", "Month"]), use_container_width=True)
        st.download_button("Download Overlap Table", ov_f.drop(columns=["Year", "Month"]).to_csv(index=False).encode("utf-8"), "overlaps.csv")

    if backtest_tab:
        backtest_results, interval_analysis, overlap_analysis, insights, _ = st.session_state["backtest_results"]
        with backtest_tab:
            st.subheader("Interval Performance Analysis")
            if insights: st.info("\n\n".join(insights))
            if interval_analysis is not None and not interval_analysis.empty:
                st.dataframe(interval_analysis.sort_values("Success Rate %", ascending=False), use_container_width=True)
                st.download_button("Download Interval Analysis", interval_analysis.to_csv(index=False).encode("utf-8"), "interval_analysis.csv")
            if overlap_analysis is not None and not overlap_analysis.empty:
                st.subheader("Success Rate by Overlap Count")
                st.dataframe(overlap_analysis.sort_values("Overlap Count", ascending=False), use_container_width=True)
                st.download_button("Download Overlap Analysis", overlap_analysis.to_csv(index=False).encode("utf-8"), "overlap_analysis.csv")
            if backtest_results is not None:
                if st.checkbox("Show detailed validation results"):
                    st.subheader("Detailed Validation Results")
                    df = backtest_results[['source_date', 'interval', 'projected_date', 'success', 'candles_to_reversal', 'prior_trend', 'reason']]
                    df['source_date'] = df['source_date'].dt.strftime(date_fmt)
                    df['projected_date'] = df['projected_date'].dt.strftime(date_fmt)
                    st.dataframe(df, use_container_width=True)

    # ----- Chart -----
    fig = go.Figure()
    fig.add_trace(go.Candlestick(x=price_df.index, open=price_df["Open"], high=price_df["High"], low=price_df["Low"], close=price_df["Close"], name="Price"))
    for t, color, sym in [("H", "red", "triangle-up"), ("L", "green", "triangle-down")]:
        pivs = pivots_df.query(f'type == "{t}"')
        fig.add_trace(go.Scatter(x=pivs["idx"], y=pivs["price"], mode="markers", marker=dict(symbol=sym, size=9, color=color), name=f"Pivot {t}"))
    if triangle_settings.get("enabled") and triangle_settings.get("show_overlays"):
        for _, pivot in pivots_df.iterrows():
            if "triangle_info" in pivot and pd.notna(pivot.get("triangle_info")):
                info = pivot["triangle_info"]
                fig.add_trace(go.Scatter(x=[info["left_base_idx"], pivot["idx"], info["right_base_idx"], info["left_base_idx"]],
                                         y=[info["left_base_price"], pivot["price"], info["right_base_price"], info["left_base_price"]],
                                         mode="lines", line=dict(color="orange", width=1, dash="dot"), showlegend=False, hoverinfo="skip"))
    for dt, cnt in overlaps_count.items():
        if cnt >= overlap_thr:
            fig.add_shape(type="line", x0=dt, x1=dt, y0=price_df["Low"].min(), y1=price_df["High"].max(), line=dict(color="purple", dash="dot"))
    fig.update_layout(height=650, xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)
