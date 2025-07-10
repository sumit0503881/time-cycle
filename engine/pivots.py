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
        window_prev_high = highs[i - rng:i]
        window_next_high = highs[i:i + rng + 1]  # include pivot bar
        window_prev_low  = lows[i - rng:i]
        window_next_low  = lows[i:i + rng + 1]  # include pivot bar

        # Pivot High
        if highs[i] > window_prev_high.max() and highs[i] > window_next_high[1:].max():
            move_down = highs[i] - window_next_low.min()
            if move_down >= min_move:
                pivots.append((idx[i], "H", highs[i], move_down))

        # Pivot Low
        if lows[i] < window_prev_low.min() and lows[i] < window_next_low[1:].min():
            move_up = window_next_high.max() - lows[i]
            if move_up >= min_move:
                pivots.append((idx[i], "L", lows[i], move_up))

    piv_df = pd.DataFrame(pivots, columns=["idx", "type", "price", "abs_move"])
    return piv_df
