# =============================================================
# File: engine/backtesting.py – Projection Validation & Analysis
# Created: December 2024
# =============================================================
from __future__ import annotations
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from .debugger import log_exceptions


@log_exceptions
def get_trend_before(
    price_data: pd.DataFrame,
    projected_date: pd.Timestamp,
    lookback: int = 5
) -> Optional[str]:
    """Determine market trend leading into projected date."""
    try:
        before_idx = price_data.index.get_loc(projected_date)
        if before_idx < lookback:
            return None
        
        before_candles = price_data.iloc[before_idx-lookback:before_idx]
        
        # Calculate trend using linear regression slope
        closes = before_candles['Close'].values
        x = np.arange(len(closes))
        slope = np.polyfit(x, closes, 1)[0]
        
        return "UP" if slope > 0 else "DOWN"
    except:
        return None


@log_exceptions
def validate_reversal(
    price_data: pd.DataFrame,
    projected_date: pd.Timestamp,
    source_pivot_type: str,
    tolerance_window: int,
    min_success_candles: int = 1
) -> Dict:
    """Check if reversal occurred within tolerance window."""
    
    # Check if projected date exists in data
    if projected_date not in price_data.index:
        return {
            'success': False,
            'reversal_date': None,
            'candles_to_reversal': 0,
            'prior_trend': None,
            'reason': 'Projected date not in data'
        }
    
    # Get trend before projected date
    prior_trend = get_trend_before(price_data, projected_date)
    if prior_trend is None:
        return {
            'success': False,
            'reversal_date': None,
            'candles_to_reversal': 0,
            'prior_trend': None,
            'reason': 'Insufficient data before projection'
        }
    
    # Get projected date candle
    proj_idx = price_data.index.get_loc(projected_date)
    proj_candle = price_data.iloc[proj_idx]
    
    # Check if we have enough future data
    if proj_idx + tolerance_window >= len(price_data):
        return {
            'success': False,
            'reversal_date': None,
            'candles_to_reversal': 0,
            'prior_trend': prior_trend,
            'reason': 'Insufficient future data'
        }
    
    # Get future candles
    future_candles = price_data.iloc[proj_idx+1:proj_idx+tolerance_window+1]
    
    reversal_candle = None
    candles_to_reversal = 0
    consecutive_count = 0
    
    for i, (date, candle) in enumerate(future_candles.iterrows(), 1):
        if prior_trend == "UP":
            # Was going up, should start going down
            if candle['Close'] < proj_candle['Close']:
                consecutive_count += 1
                if consecutive_count >= min_success_candles:
                    reversal_candle = date
                    candles_to_reversal = i - min_success_candles + 1
                    break
            else:
                consecutive_count = 0
        else:  # DOWN
            # Was going down, should start going up
            if candle['Close'] > proj_candle['Close']:
                consecutive_count += 1
                if consecutive_count >= min_success_candles:
                    reversal_candle = date
                    candles_to_reversal = i - min_success_candles + 1
                    break
            else:
                consecutive_count = 0
    
    return {
        'success': reversal_candle is not None,
        'reversal_date': reversal_candle,
        'candles_to_reversal': candles_to_reversal,
        'prior_trend': prior_trend,
        'reason': 'Success' if reversal_candle else 'No reversal within window'
    }


@log_exceptions
def analyze_all_projections(
    projections: List[Tuple[pd.Timestamp, int, pd.Timestamp]],
    price_data: pd.DataFrame,
    tolerance_window: int,
    min_success_candles: int = 1,
    lookback_candles: int = 5
) -> Tuple[List[Dict], Dict]:
    """Validate all projections and analyze by interval."""
    
    validation_results = []
    
    for source_date, interval, proj_date in projections:
        # Determine source pivot type from price data
        source_idx = price_data.index.get_loc(source_date)
        
        # Simple heuristic: if price is near high, it's a high pivot
        source_candle = price_data.iloc[source_idx]
        if abs(source_candle['High'] - source_candle['Close']) < abs(source_candle['Close'] - source_candle['Low']):
            source_type = "H"
        else:
            source_type = "L"
        
        result = validate_reversal(
            price_data, 
            proj_date, 
            source_type, 
            tolerance_window,
            min_success_candles
        )
        
        result['source_date'] = source_date
        result['interval'] = interval
        result['projected_date'] = proj_date
        
        validation_results.append(result)
    
    # Analyze by interval
    interval_stats = analyze_intervals(validation_results)
    
    return validation_results, interval_stats


@log_exceptions
def analyze_intervals(validation_results: List[Dict]) -> Dict:
    """Find which intervals appear most in successful predictions."""
    
    interval_stats = {}
    
    for result in validation_results:
        interval = result['interval']
        
        if interval not in interval_stats:
            interval_stats[interval] = {
                'total_count': 0,
                'success_count': 0,
                'immediate_reversals': 0,  # within 1 candle
                'total_candles_to_reversal': 0,
                'reversal_dates': []
            }
        
        interval_stats[interval]['total_count'] += 1
        
        if result['success']:
            interval_stats[interval]['success_count'] += 1
            interval_stats[interval]['total_candles_to_reversal'] += result['candles_to_reversal']
            interval_stats[interval]['reversal_dates'].append(result['projected_date'])
            
            if result['candles_to_reversal'] == 1:
                interval_stats[interval]['immediate_reversals'] += 1
    
    # Calculate success rates and averages
    for interval, stats in interval_stats.items():
        stats['success_rate'] = (stats['success_count'] / stats['total_count'] * 100) if stats['total_count'] > 0 else 0
        stats['immediate_reversal_rate'] = (stats['immediate_reversals'] / stats['total_count'] * 100) if stats['total_count'] > 0 else 0
        if stats['success_count'] > 0:
            stats['avg_candles_to_reversal'] = stats['total_candles_to_reversal'] / stats['success_count']
        else:
            stats['avg_candles_to_reversal'] = 0
    
    return interval_stats


@log_exceptions
def generate_insights(interval_stats: Dict, validation_results: List[Dict]) -> List[str]:
    """Generate meaningful insights from backtesting results."""
    
    insights = []
    
    # Sort intervals by success rate
    sorted_intervals = sorted(
        interval_stats.items(), 
        key=lambda x: x[1]['success_rate'], 
        reverse=True
    )
    
    # Top performing intervals
    if sorted_intervals:
        top_intervals = [f"{iv} ({stats['success_rate']:.1f}%)" 
                        for iv, stats in sorted_intervals[:3] 
                        if stats['success_rate'] > 50]
        if top_intervals:
            insights.append(f"Top performing intervals: {', '.join(top_intervals)}")
    
    # Immediate reversal rate
    total_success = sum(1 for r in validation_results if r['success'])
    immediate_count = sum(1 for r in validation_results if r['success'] and r['candles_to_reversal'] == 1)
    if total_success > 0:
        immediate_rate = immediate_count / total_success * 100
        insights.append(f"{immediate_rate:.0f}% of successful reversals occurred immediately (next candle)")
    
    # Average reversal speed
    all_candles_to_reversal = [r['candles_to_reversal'] for r in validation_results if r['success']]
    if all_candles_to_reversal:
        avg_speed = np.mean(all_candles_to_reversal)
        insights.append(f"Average reversal occurs within {avg_speed:.1f} candles of projection")
    
    # Overall success rate
    total_projections = len(validation_results)
    if total_projections > 0:
        overall_success_rate = total_success / total_projections * 100
        insights.append(f"Overall success rate: {overall_success_rate:.1f}% ({total_success}/{total_projections})")
    
    return insights
