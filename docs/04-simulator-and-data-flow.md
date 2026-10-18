# 04 - Simulator & Data Flow

> **Status:** Implementation Complete / Unit Tests Verified (8/8 Passed)

---

## 1. IoT Simulator Design (VIT Vellore Campus)
The simulator (`simulator/simulate_bins.py`) simulates a network of **12 smart bins** deployed across the **VIT Vellore** campus grounds:
* **Bin ID:** `BIN-001` through `BIN-012`.
* **Locations:** Technology Tower (TT), Periyar Library, Silver Jubilee Tower (SJT), Main Building (MB), Anna Auditorium, Gazebo Canteen, SMV Block, Outdoor Stadium, Men's & Ladies' Hostels, and Sports Complex.
* **Coordinates:** High-precision GPS latitude ($12.968^\circ\text{N} - 12.973^\circ\text{N}$) and longitude ($79.155^\circ\text{E} - 79.165^\circ\text{E}$).
* **Fill Level:** Current fill percentage bounded to $[0.0, 100.0\%]$.
* **Timestamp:** Simulated epoch millisecond timestamp.
* **Fill Rate:** Accumulation rate ($2.5\% - 9.0\%$ per hour) modeling varying foot traffic.
* **Sensor Noise:** Gaussian perturbation ($\sigma = 0.5\%$) plus occasional sensor spikes ($\pm 2.5\%$).
* **Collection Emptying Simulation:** Automatically empties full bins ($> 99.5\%$) back to $5.0\% - 10.0\%$ baseline to verify the alert reset hysteresis ($< 50\%$).

---

## 2. Seed Data Structure (`bins_seed.json`)
The 12 monitored campus bins are defined in [`simulator/bins_seed.json`](file:///c:/Users/asus/Desktop/aws%20project/simulator/bins_seed.json):

```json
[
  {
    "bin_id": "BIN-001",
    "location_name": "Periyar Central Library Plaza",
    "latitude": 12.9698,
    "longitude": 79.1559,
    "capacity_liters": 120,
    "initial_fill": 35.0,
    "fill_rate_per_hour": 5.0
  },
  {
    "bin_id": "BIN-002",
    "location_name": "Technology Tower (TT) Food Court",
    "latitude": 12.9705,
    "longitude": 79.1595,
    "capacity_liters": 150,
    "initial_fill": 62.0,
    "fill_rate_per_hour": 8.5
  }
]
```

---

## 3. Simulation Loop & Noise Model
Each iteration (tick) of the simulator executes:

1. **Delta Calculation:**
   $$\Delta \text{fill} = \left(\frac{\text{fill\_rate\_per\_hour} \times \Delta t_{\text{seconds}}}{3600}\right) + \mathcal{N}(0, \sigma^2)$$
   where $\sigma = 0.5\%$.

2. **Occasional Noise Spikes:**
   With $5\%$ probability, injects an obstacle perturbation of $\pm 2.5\%$.

3. **Boundary Clamping:**
   $$\text{fill\_level} = \min(100.0, \max(0.0, \text{fill\_level} + \Delta \text{fill}))$$

4. **Emptying Simulation:**
   When a bin reaches $\ge 99.5\%$, resets to $5.0\% - 10.0\%$, testing the alert reset hysteresis ($< 50\%$).

5. **Network Dispatch:**
   Serializes readings into `{"readings": [...]}` and issues HTTP `POST` to the configured `SIMULATOR_API_ENDPOINT` with graceful retry and error handling.

---

## 4. Execution Modes
The simulator supports both continuous demonstration and finite test runs:
* **Continuous mode (default):**
  ```powershell
  .venv\Scripts\python.exe simulator/simulate_bins.py
  ```
* **Finite run mode (e.g. 5 ticks):**
  ```powershell
  .venv\Scripts\python.exe simulator/simulate_bins.py --ticks 5 --interval 5.0
  ```
* **Dry-run mode (print without sending HTTP POST):**
  ```powershell
  .venv\Scripts\python.exe simulator/simulate_bins.py --dry-run --ticks 2
  ```

---

## 5. Verification Status
* **Configuration:** [`simulator/config.py`](file:///c:/Users/asus/Desktop/aws%20project/simulator/config.py)
* **Seed Coordinates:** [`simulator/bins_seed.json`](file:///c:/Users/asus/Desktop/aws%20project/simulator/bins_seed.json)
* **Simulator Engine:** [`simulator/simulate_bins.py`](file:///c:/Users/asus/Desktop/aws%20project/simulator/simulate_bins.py)
* **Unit Tests:** [`tests/test_simulator.py`](file:///c:/Users/asus/Desktop/aws%20project/tests/test_simulator.py)
* **Status:** **VERIFIED** (8/8 tests passing in offline test suite).
