# =============================================================
# File: engine/pivots.py – Corrected for Absolute Movement (simple syntax)
# =============================================================
from __future__ import annotations
import pandas as pd
import numpy as np
from .debugger import log_exceptions

@log_exceptions
def detect_pivots(
    df: pd.DataFrame,
    pivot_range: int,
    min_move: float,
    tol_pct: float = 0.0,
) -> pd.DataFrame:
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
            abs_move = min(move_down_prev, move_down_next)
            diff = abs(move_down_prev - move_down_next)

            min_move_ok = move_down_prev >= min_move and move_down_next >= min_move
            tol_ok = True
            if tol_pct > 0:
                tol_ok = diff <= (tol_pct / 100.0) * abs_move

            valid = min_move_ok and tol_ok
            reason = []
            if not min_move_ok:
                reason.append("min move miss")
            if tol_pct > 0 and not tol_ok:
                reason.append("triangle mismatch")
            pivots.append(
                (
                    idx[i],
                    "H",
                    highs[i],
                    move_down_prev,
                    move_down_next,
                    abs_move,
                    valid,
                    ", ".join(reason) if reason else "",
                )
            )

        # Pivot Low
        if lows[i] < window_prev_low.min() and lows[i] < window_next_low.min():
            move_up_prev = window_prev_high.max() - lows[i]
            move_up_next = window_next_high.max() - lows[i]
            abs_move = min(move_up_prev, move_up_next)
            diff = abs(move_up_prev - move_up_next)

            min_move_ok = move_up_prev >= min_move and move_up_next >= min_move
            tol_ok = True
            if tol_pct > 0:
                tol_ok = diff <= (tol_pct / 100.0) * abs_move

            valid = min_move_ok and tol_ok
            reason = []
            if not min_move_ok:
                reason.append("min move miss")
            if tol_pct > 0 and not tol_ok:
                reason.append("triangle mismatch")
            pivots.append(
                (
                    idx[i],
                    "L",
                    lows[i],
                    move_up_prev,
                    move_up_next,
                    abs_move,
                    valid,
                    ", ".join(reason) if reason else "",
                )
            )

    piv_df = pd.DataFrame(
        pivots,
        columns=[
            "idx",
            "type",
            "price",
            "move_prev",
            "move_next",
            "abs_move",
            "valid",
            "reason",
        ],
    )
    return piv_df
