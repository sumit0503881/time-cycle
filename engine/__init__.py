# ─────────────────────────────────────────────────────────────
# File: engine/__init__.py
# ─────────────────────────────────────────────────────────────
"""Engine package — exposes top‑level helpers."""
from .pivots import detect_pivots
from .intervals import project_intervals, count_overlaps
from .holidays import load_holiday_calendar, is_business_day
from .debugger import setup_debugger, log_exceptions
from .triangle import filter_pivots_by_triangle, analyze_triangle_formation
from .backtesting import analyze_all_projections, generate_insights

__all__ = [
    "detect_pivots",
    "project_intervals",
    "count_overlaps",
    "load_holiday_calendar",
    "is_business_day",
    "setup_debugger",
    "log_exceptions",
    "filter_pivots_by_triangle",
    "analyze_triangle_formation",
    "analyze_all_projections",
    "generate_insights",
]
