# =============================================================
# File: engine/intervals.py – Corrected holiday-aware projection
# Corrected: 10-May-2025 (Accurate Bar Projection + Future Projection Enabled)
# =============================================================
from __future__ import annotations
import pandas as pd
from .holidays import is_business_day
from .debugger import log_exceptions

@log_exceptions
def project_intervals(
    pivots_df: pd.DataFrame,
    intervals: list[int],
    use_bars: bool,
    original_df: pd.DataFrame,
    holiday_set: set[pd.Timestamp],
) -> list[tuple[pd.Timestamp, int, pd.Timestamp]]:
    results: list[tuple[pd.Timestamp, int, pd.Timestamp]] = []

    if use_bars:
        # 1) Restrict to market hours (intraday bars)
        df_bars = original_df.between_time("09:15", "15:29")

        # 2) Exclude weekends & holidays
        mask = df_bars.index.to_series().apply(
            lambda ts: ts.weekday() < 5 and is_business_day(ts, holiday_set)
        )
        df_bars = df_bars[mask]

        # 3) Determine bar-size in minutes from filtered data
        interval_minutes = int((df_bars.index[1] - df_bars.index[0]).total_seconds() // 60)

        # Function to get the next valid trading day
        def next_valid_day(current_time, holiday_set):
            next_day = current_time + pd.Timedelta(days=1)
            while next_day.weekday() >= 5 or next_day.date() in holiday_set:
                next_day += pd.Timedelta(days=1)
            return next_day.replace(hour=9, minute=15)

        # 4) Project for each pivot & each interval
        for pivot_ts in pivots_df["idx"].sort_values():
            for iv in intervals:
                total_bars = iv
                projected_time = pivot_ts

                while total_bars > 0:
                    # Last valid bar start today (even if beyond data)
                    last_start = projected_time.normalize().replace(
                        hour=15, minute=30 - interval_minutes)

                    if projected_time >= last_start:
                        projected_time = next_valid_day(projected_time, holiday_set)
                        continue

                    # Calculate available bars today (or future)
                    bars_today = int((last_start - projected_time).total_seconds() // (interval_minutes * 60))

                    if bars_today <= 0:
                        projected_time = next_valid_day(projected_time, holiday_set)
                        continue

                    # Consume bars (either all remaining or today's capacity)
                    bars_to_consume = min(total_bars, bars_today)
                    projected_time += pd.Timedelta(minutes=bars_to_consume * interval_minutes)
                    total_bars -= bars_to_consume

                # Append even if future date
                results.append((pivot_ts, iv, projected_time))

        return results

    # --- Calendar-days mode (unchanged) ------------------------
    for pivot_ts in pivots_df["idx"].sort_values():
        for iv in intervals:
            projected = pivot_ts + pd.Timedelta(days=iv)
            if is_business_day(projected, holiday_set):
                results.append((pivot_ts, iv, projected))
            else:
                before = projected
                after  = projected
                while not is_business_day(before, holiday_set):
                    before -= pd.Timedelta(days=1)
                while not is_business_day(after, holiday_set):
                    after  += pd.Timedelta(days=1)
                results.append((pivot_ts, iv, before))

    return results

def count_overlaps(hits: list[tuple[pd.Timestamp, int, pd.Timestamp]]) -> dict[pd.Timestamp, int]:
    from collections import Counter
    return dict(Counter(hit[2] for hit in hits))
