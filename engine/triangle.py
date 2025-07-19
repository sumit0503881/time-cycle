# =============================================================
# File: engine/triangle.py – Triangle-based Pivot Detection
# Created: December 2024
# =============================================================
from __future__ import annotations
import pandas as pd
import numpy as np
from typing import Tuple, Optional
from .debugger import log_exceptions


@log_exceptions
def calculate_distance(
    point1: Tuple[pd.Timestamp, float],
    point2: Tuple[pd.Timestamp, float],
    time_scale: float
) -> float:
    """Calculate normalized distance between two points (time, price)."""
    time_diff = abs((point2[0] - point1[0]).total_seconds() / 86400)  # days
    price_diff = abs(point2[1] - point1[1])
    return np.sqrt((time_diff * time_scale) ** 2 + price_diff ** 2)


@log_exceptions
def classify_triangle(
    sides: Tuple[float, float, float],
    tolerance: float
) -> str:
    """Classify triangle based on side lengths."""
    al, ar, lr = sorted(sides)
    
    # Check equilateral
    if lr / al <= 1 + tolerance / 100:
        return "equilateral"
    
    # Check isosceles
    if (ar / al <= 1 + tolerance / 100 or
        lr / ar <= 1 + tolerance / 100):
        return "isosceles"
    
    return "scalene"


@log_exceptions
def calculate_symmetry_score(
    pivot_idx: int,
    left_idx: int,
    right_idx: int,
    pivot_price: float,
    left_price: float,
    right_price: float
) -> float:
    """Calculate symmetry score (0-100%) for a triangle formation."""
    # Time symmetry
    left_duration = pivot_idx - left_idx
    right_duration = right_idx - pivot_idx
    time_symmetry = 100 * (1 - abs(left_duration - right_duration) / 
                           max(left_duration, right_duration))
    
    # Price movement symmetry
    left_move = abs(pivot_price - left_price)
    right_move = abs(pivot_price - right_price)
    move_symmetry = 100 * (1 - abs(left_move - right_move) / 
                           max(left_move, right_move))
    
    return (time_symmetry + move_symmetry) / 2


@log_exceptions
def analyze_triangle_formation(
    df: pd.DataFrame,
    pivot_idx: int,
    pivot_range: int,
    pivot_price: float,
    time_scale: float,
    tolerance: float
) -> Optional[dict]:
    """Analyze triangle formation for a potential pivot high."""
    # Find left and right base points (lowest lows)
    left_start = max(0, pivot_idx - pivot_range)
    left_window = df.iloc[left_start:pivot_idx]
    left_idx = left_window["Low"].idxmin()
    left_price = df.loc[left_idx, "Low"]
    left_bar_idx = df.index.get_loc(left_idx)
    
    right_end = min(len(df), pivot_idx + pivot_range + 1)
    right_window = df.iloc[pivot_idx + 1:right_end]
    if right_window.empty:
        return None
    right_idx = right_window["Low"].idxmin()
    right_price = df.loc[right_idx, "Low"]
    right_bar_idx = df.index.get_loc(right_idx)
    
    # Calculate triangle sides
    apex = (df.index[pivot_idx], pivot_price)
    left_base = (left_idx, left_price)
    right_base = (right_idx, right_price)
    
    al = calculate_distance(apex, left_base, time_scale)
    ar = calculate_distance(apex, right_base, time_scale)
    lr = calculate_distance(left_base, right_base, time_scale)
    
    # Classify triangle
    triangle_type = classify_triangle((al, ar, lr), tolerance)
    
    # Calculate symmetry score
    symmetry = calculate_symmetry_score(
        pivot_idx, left_bar_idx, right_bar_idx,
        pivot_price, left_price, right_price
    )
    
    return {
        "type": triangle_type,
        "symmetry_score": symmetry,
        "left_base_idx": left_idx,
        "left_base_price": left_price,
        "right_base_idx": right_idx,
        "right_base_price": right_price,
        "sides": {"AL": al, "AR": ar, "LR": lr}
    }


@log_exceptions
def filter_pivots_by_triangle(
    df: pd.DataFrame,
    pivots_df: pd.DataFrame,
    triangle_settings: dict
) -> pd.DataFrame:
    """Filter pivots based on triangle formation criteria."""
    if not triangle_settings.get("enabled", False):
        return pivots_df
    
    filtered_pivots = []
    triangle_types = triangle_settings.get("types", ["equilateral", "isosceles", "scalene"])
    time_scale = triangle_settings.get("time_scale", 10)
    tolerance = triangle_settings.get("tolerance", 10)
    min_symmetry = triangle_settings.get("min_symmetry", 0)
    pivot_range = triangle_settings.get("pivot_range", 5)
    
    for _, pivot in pivots_df.iterrows():
        if pivot["type"] != "H":  # Only analyze pivot highs
            filtered_pivots.append(pivot)
            continue
        
        pivot_idx = df.index.get_loc(pivot["idx"])
        triangle_info = analyze_triangle_formation(
            df, pivot_idx, pivot_range, pivot["price"], 
            time_scale, tolerance
        )
        
        if triangle_info is None:
            continue
        
        # Check if triangle meets criteria
        if (triangle_info["type"] in triangle_types and
            triangle_info["symmetry_score"] >= min_symmetry):
            # Add triangle info to pivot
            enhanced_pivot = pivot.copy()
            enhanced_pivot["triangle_type"] = triangle_info["type"]
            enhanced_pivot["symmetry_score"] = triangle_info["symmetry_score"]
            enhanced_pivot["triangle_info"] = triangle_info
            filtered_pivots.append(enhanced_pivot)
    
    return pd.DataFrame(filtered_pivots)
