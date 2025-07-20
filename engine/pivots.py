# =============================================================
# File: engine/pivots.py – Enhanced with validity tracking and rejection reasons
# =============================================================
from __future__ import annotations
import pandas as pd
import numpy as np
from .debugger import log_exceptions

@log_exceptions
def detect_pivots(df: pd.DataFrame, pivot_range: int, min_move: float, return_all: bool = True) -> pd.DataFrame:
    """
    Detect pivot highs and lows with validity tracking.
    
    Args:
        df: Price dataframe with OHLC data
        pivot_range: Number of bars to check on each side
        min_move: Minimum price movement required
        return_all: If True, return all potential pivots with validity status
                   If False, return only valid pivots (legacy behavior)
    
    Returns:
        DataFrame with columns: idx, type, price, abs_move, valid, rejection_reason
    """
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

        # Check Pivot High
        is_higher_than_prev = highs[i] > window_prev_high.max()
        is_higher_than_next = highs[i] > window_next_high.max()
        
        if is_higher_than_prev and is_higher_than_next:
            # Valid pivot high pattern, check minimum movement
            move_down_prev = highs[i] - window_prev_low.min()
            move_down_next = highs[i] - window_next_low.min()
            min_move_achieved = move_down_prev >= min_move and move_down_next >= min_move
            
            if min_move_achieved or return_all:
                pivots.append({
                    "idx": idx[i],
                    "type": "H",
                    "price": highs[i],
                    "abs_move": min(move_down_prev, move_down_next),
                    "valid": min_move_achieved,
                    "rejection_reason": None if min_move_achieved else 
                        f"Insufficient movement: prev={move_down_prev:.2f}, next={move_down_next:.2f} < {min_move}"
                })
        elif return_all and (is_higher_than_prev or is_higher_than_next):
            # Potential pivot high that failed basic criteria
            rejection_parts = []
            if not is_higher_than_prev:
                max_prev = window_prev_high.max()
                rejection_parts.append(f"Not higher than previous {rng} bars (max={max_prev:.2f})")
            if not is_higher_than_next:
                max_next = window_next_high.max()
                rejection_parts.append(f"Not higher than next {rng} bars (max={max_next:.2f})")
            
            pivots.append({
                "idx": idx[i],
                "type": "H",
                "price": highs[i],
                "abs_move": 0,
                "valid": False,
                "rejection_reason": "; ".join(rejection_parts)
            })

        # Check Pivot Low
        is_lower_than_prev = lows[i] < window_prev_low.min()
        is_lower_than_next = lows[i] < window_next_low.min()
        
        if is_lower_than_prev and is_lower_than_next:
            # Valid pivot low pattern, check minimum movement
            move_up_prev = window_prev_high.max() - lows[i]
            move_up_next = window_next_high.max() - lows[i]
            min_move_achieved = move_up_prev >= min_move and move_up_next >= min_move
            
            if min_move_achieved or return_all:
                pivots.append({
                    "idx": idx[i],
                    "type": "L",
                    "price": lows[i],
                    "abs_move": min(move_up_prev, move_up_next),
                    "valid": min_move_achieved,
                    "rejection_reason": None if min_move_achieved else
                        f"Insufficient movement: prev={move_up_prev:.2f}, next={move_up_next:.2f} < {min_move}"
                })
        elif return_all and (is_lower_than_prev or is_lower_than_next):
            # Potential pivot low that failed basic criteria
            rejection_parts = []
            if not is_lower_than_prev:
                min_prev = window_prev_low.min()
                rejection_parts.append(f"Not lower than previous {rng} bars (min={min_prev:.2f})")
            if not is_lower_than_next:
                min_next = window_next_low.min()
                rejection_parts.append(f"Not lower than next {rng} bars (min={min_next:.2f})")
            
            pivots.append({
                "idx": idx[i],
                "type": "L",
                "price": lows[i],
                "abs_move": 0,
                "valid": False,
                "rejection_reason": "; ".join(rejection_parts)
            })

    piv_df = pd.DataFrame(pivots)
    
    # For backward compatibility, filter to valid pivots if return_all is False
    if not return_all and not piv_df.empty:
        piv_df = piv_df[piv_df["valid"]].drop(columns=["valid", "rejection_reason"])
    
    return piv_df
