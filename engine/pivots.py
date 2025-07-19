# =============================================================
# File: engine/pivots.py – Corrected for Absolute Movement (simple syntax)
# =============================================================
from __future__ import annotations
import pandas as pd
import numpy as np
from .debugger import log_exceptions

@log_exceptions
def detect_pivots(df: pd.DataFrame, pivot_range: int, min_move: float) -> pd.DataFrame:
    highs = df["High"].values
    lows = df["Low"].values
    idx = df.index.to_numpy()
    rng = pivot_range
    pivots = []

    for i in range(rng, len(df) - rng):
        # windows excluding the pivot bar for symmetry
        window_prev_high = highs[i - rng:i]
        window_next_high = highs[i + 1 : i + rng + 1]
        window_prev_low  = lows[i - rng:i]
        window_next_low  = lows[i + 1 : i + rng + 1]

        # Pivot High
        if highs[i] > window_prev_high.max() and highs[i] > window_next_high.max():
            move_down_prev = highs[i] - window_prev_low.min()
            move_down_next = highs[i] - window_next_low.min()
            if move_down_prev >= min_move and move_down_next >= min_move:
                pivots.append((idx[i], "H", highs[i], min(move_down_prev, move_down_next)))

        # Pivot Low
        if lows[i] < window_prev_low.min() and lows[i] < window_next_low.min():
            move_up_prev = window_prev_high.max() - lows[i]
            move_up_next = window_next_high.max() - lows[i]
            if move_up_prev >= min_move and move_up_next >= min_move:
                pivots.append((idx[i], "L", lows[i], min(move_up_prev, move_up_next)))

    piv_df = pd.DataFrame(pivots, columns=["idx", "type", "price", "abs_move"])
    return piv_df
