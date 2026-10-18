# 05 - Analytics & Route Optimization

> **Status:** Implementation Complete / Unit Tests Verified (7/7 Passed)

---

## 1. Analytics Architecture Overview
The `waste-analytics` Lambda function (`lambdas/waste_analytics/lambda_function.py`) executes on a 15-minute schedule managed by Amazon EventBridge. It orchestrates:
1. **Reset Filtering:** Discards historical readings prior to the latest emptying event (detected when fill level drops by $\ge 15\%$).
2. **Fill Rate Forecasting:** Fits an Ordinary Least Squares (OLS) linear regression model over recent active readings to compute fill rate (%/hr) and estimate hours until **90% capacity**.
3. **Priority Scoring:** Computes an urgency score $P \in [0, 100]$ incorporating current fill level and estimated time to overflow.
4. **Stop Selection:** Filters up to 8 bins with priority score $\ge 60.0$.
5. **Route Optimization:** Solves the Traveling Salesperson Problem (TSP) using Nearest-Neighbour followed by 2-Opt edge swaps.
6. **Route Persistence:** Stores the calculated route in DynamoDB `WasteBins` under `bin_id = "__ROUTE__"`.

---

## 2. Linear Regression (Hours to 90% Capacity)

### A. Reset Detection
```python
# Readings before a sharp drop (>= 15%) belong to previous collection cycles
active_readings = filter_readings_after_latest_reset(readings, drop_threshold=15.0)
```

### B. Ordinary Least Squares (OLS) Formula
Given $N$ timestamp-fill pairs $(t_i, y_i)$:
$$\text{Slope } m = \frac{N \sum (t_i y_i) - \sum t_i \sum y_i}{N \sum t_i^2 - (\sum t_i)^2}$$
$$\text{Intercept } c = \frac{\sum y_i - m \sum t_i}{N}$$

$$\text{Fill Rate (\%/hr)} = m \times 3600$$

### C. Hours to 90% Forecast
$$\text{Hours to 90\%} = \frac{90.0 - \text{current\_fill}}{m \times 3600}$$

* **Edge Cases Handled:**
  * $N < 2$: Insufficient data $\to$ returns `None`.
  * $m \le 0$: Flat or declining fill $\to$ returns `None`.
  * $\text{current\_fill} \ge 90\%$: Overflow imminent $\to$ returns `0.0`.

---

## 3. Priority Scoring Formula
$$P = 0.6 \cdot (\text{current\_fill}) + \frac{40.0}{\text{hours\_to\_90} + 0.5}$$
* Clamped strictly between $0.0$ and $100.0$.
* If $\text{current\_fill} \ge 90.0\%$, $P = 100.0$.
* If $\text{hours\_to\_90}$ is `None`, $P = \min(100.0, \text{current\_fill})$.
* Bins with $P \ge 60.0$ qualify for the collection route.

---

## 4. Route Optimization (Nearest-Neighbour + 2-Opt)

1. **Depot Node:** Configured centrally (default: $40.7100^\circ\text{ N}, -74.0100^\circ\text{ W}$).
2. **Haversine Distance:** Used to construct pairwise great-circle distances.
3. **Nearest-Neighbour:** Greedily links the nearest unvisited prioritized bin to establish a closed baseline tour.
4. **2-Opt Optimization:** Iteratively evaluates pairs of non-adjacent edges $(i, i+1)$ and $(j, j+1)$ and reverses the sub-tour segment if:
   $$\Delta d = (d_{i,j} + d_{i+1, j+1}) - (d_{i, i+1} + d_{j, j+1}) < 0$$
   Guarantees that optimized tour distance $\le$ nearest-neighbour distance.

---

## 5. Persistence Under `bin_id = "__ROUTE__"`
The finalized tour is persisted to `WasteBins` with `bin_id = "__ROUTE__"`:
```json
{
  "bin_id": "__ROUTE__",
  "generated_at": "2026-10-17T17:30:00Z",
  "total_distance_km": 12.4,
  "num_bins_serviced": 4,
  "depot": {
    "name": "Central Depot",
    "latitude": 40.7100,
    "longitude": -74.0100
  },
  "stops": [
    {
      "stop_number": 1,
      "bin_id": "BIN-004",
      "latitude": 40.7140,
      "longitude": -74.0080,
      "fill_level": 91.0,
      "priority_score": 100.0
    }
  ]
}
```

---

## 6. Verification Status
* **Predictor Module:** [`lambdas/waste_analytics/predictor.py`](file:///c:/Users/asus/Desktop/aws%20project/lambdas/waste_analytics/predictor.py)
* **Optimizer Module:** [`lambdas/waste_analytics/optimizer.py`](file:///c:/Users/asus/Desktop/aws%20project/lambdas/waste_analytics/optimizer.py)
* **Lambda Handler:** [`lambdas/waste_analytics/lambda_function.py`](file:///c:/Users/asus/Desktop/aws%20project/lambdas/waste_analytics/lambda_function.py)
* **Unit Tests:** [`tests/test_waste_analytics.py`](file:///c:/Users/asus/Desktop/aws%20project/tests/test_waste_analytics.py)
* **Status:** **VERIFIED** (7/7 tests passing in offline test suite).
