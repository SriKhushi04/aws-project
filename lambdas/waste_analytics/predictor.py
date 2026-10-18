"""Fill-rate forecasting and priority scoring using Ordinary Least Squares (OLS) regression."""
from typing import List, Dict, Any, Tuple, Optional

def filter_readings_after_latest_reset(
    readings: List[Dict[str, Any]],
    drop_threshold: float = 15.0
) -> List[Dict[str, Any]]:
    """
    Filter readings to include only those after the most recent emptying/reset event.
    An emptying event is detected when a reading drops by >= drop_threshold % compared to the previous reading.
    Assumes readings are ordered chronologically.
    """
    if not readings:
        return []

    latest_reset_index = 0
    for i in range(1, len(readings)):
        prev_fill = float(readings[i - 1].get("fill_level", 0.0))
        curr_fill = float(readings[i].get("fill_level", 0.0))
        # If fill drops significantly, a collection/emptying event took place
        if curr_fill < prev_fill - drop_threshold:
            latest_reset_index = i

    return readings[latest_reset_index:]

def fit_linear_regression(
    readings: List[Dict[str, Any]]
) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """
    Perform Ordinary Least Squares (OLS) linear regression on readings.
    Returns: (slope_per_sec, intercept, fill_rate_per_hour)
    Returns (None, None, None) if insufficient data (N < 2) or zero variance in timestamps.
    """
    if len(readings) < 2:
        return None, None, None

    # Use first reading timestamp as reference t0 to prevent float precision issues
    t0 = float(readings[0]["timestamp"]) / 1000.0  # epoch seconds
    x_vals: List[float] = []
    y_vals: List[float] = []

    for r in readings:
        t_sec = float(r["timestamp"]) / 1000.0 - t0
        x_vals.append(t_sec)
        y_vals.append(float(r["fill_level"]))

    n = len(x_vals)
    sum_x = sum(x_vals)
    sum_y = sum(y_vals)
    sum_xx = sum(x * x for x in x_vals)
    sum_xy = sum(x * y for x, y in zip(x_vals, y_vals))

    denom = (n * sum_xx) - (sum_x * sum_x)
    if abs(denom) < 1e-9:
        return None, None, None

    slope_per_sec = ((n * sum_xy) - (sum_x * sum_y)) / denom
    intercept = (sum_y - (slope_per_sec * sum_x)) / n
    fill_rate_per_hour = slope_per_sec * 3600.0

    return slope_per_sec, intercept, fill_rate_per_hour

def predict_hours_to_capacity(
    current_fill: float,
    slope_per_sec: Optional[float],
    target_capacity: float = 90.0
) -> Optional[float]:
    """
    Estimate hours remaining until bin reaches target_capacity (default: 90.0%).
    Edge cases:
    - current_fill >= target_capacity: returns 0.0
    - slope_per_sec is None or <= 0: returns None (no impending overflow)
    """
    if current_fill >= target_capacity:
        return 0.0

    if slope_per_sec is None or slope_per_sec <= 0.0:
        return None

    sec_to_target = (target_capacity - current_fill) / slope_per_sec
    hours = max(0.0, sec_to_target / 3600.0)
    return round(hours, 2)

def calculate_priority_score(
    current_fill: float,
    hours_to_90: Optional[float]
) -> float:
    """
    Calculate an urgency priority score P in [0.0, 100.0].
    Formula:
      P = w1 * (current_fill) + w2 * max(0, 1 / (hours_to_90 + epsilon))
    where w1 = 0.6, w2 = 40.0, epsilon = 0.5.
    If already >= 90%, score is set to 100.0.
    If hours_to_90 is None, priority relies purely on current_fill.
    """
    if current_fill >= 90.0:
        return 100.0

    fill_component = 0.6 * max(0.0, min(100.0, current_fill))

    if hours_to_90 is None:
        # Scale fill component to [0, 100] when no rate data is available
        return round(min(100.0, current_fill), 2)

    urgency_component = 40.0 / (hours_to_90 + 0.5)
    total_score = fill_component + urgency_component
    return round(max(0.0, min(100.0, total_score)), 2)

