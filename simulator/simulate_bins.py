"""IoT Smart Waste Bin Telemetry Simulator for VIT Vellore Campus.
Simulates realistic fill-rate accumulation, sensor noise, emptying events,
and dispatches readings to the API Gateway ingestion endpoint.
"""
import os
import sys

# Ensure project root is in sys.path when executed directly as a script
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import json
import time
import random
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
import requests

from simulator.config import get_simulator_config

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("WasteBinSimulator")

SEED_FILE_PATH = os.path.join(os.path.dirname(__file__), "bins_seed.json")

class WasteBinSimulator:
    def __init__(
        self,
        seed_path: Optional[str] = None,
        custom_bins: Optional[List[Dict[str, Any]]] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.config = config or get_simulator_config()
        self.seed_path = seed_path or SEED_FILE_PATH
        self.bins: List[Dict[str, Any]] = []

        if custom_bins is not None:
            self.bins = [dict(b) for b in custom_bins]
        else:
            self.load_bins()

        logger.info(f"Initialized simulator with {len(self.bins)} bins.")

    def load_bins(self) -> None:
        """Load initial bin seeds from JSON file or fall back to defaults."""
        if os.path.exists(self.seed_path):
            try:
                with open(self.seed_path, "r", encoding="utf-8") as f:
                    self.bins = json.load(f)
                logger.info(f"Loaded {len(self.bins)} bins from '{self.seed_path}'.")
                return
            except Exception as e:
                logger.error(f"Error reading '{self.seed_path}': {e}. Using fallback seeds.")

        # Fallback default seeds if file is unavailable
        self.bins = [
            {
                "bin_id": f"BIN-{i:03d}",
                "location_name": f"Campus Location {i}",
                "latitude": 12.9692 + (i * 0.0003),
                "longitude": 79.1550 + (i * 0.0008),
                "capacity_liters": 120,
                "initial_fill": float(random.randint(20, 70)),
                "fill_rate_per_hour": round(random.uniform(4.0, 9.0), 1)
            }
            for i in range(1, 13)
        ]

    def tick(self, delta_seconds: float) -> List[Dict[str, Any]]:
        """
        Advance the simulation state by delta_seconds.
        Calculates fill rate accumulation, sensor noise, and boundary resets.
        Returns a list of generated reading dictionaries.
        """
        now_dt = datetime.now(timezone.utc)
        now_ms = int(now_dt.timestamp() * 1000)
        readings: List[Dict[str, Any]] = []

        for b in self.bins:
            # 1. Initialize current fill if not already set
            if "current_fill" not in b:
                b["current_fill"] = float(b.get("initial_fill", 30.0))

            fill_rate_hr = float(b.get("fill_rate_per_hour", 5.0))
            # Delta fill based on elapsed time
            fill_delta = (fill_rate_hr * delta_seconds) / 3600.0

            # 2. Check if bin has reached capacity (>= 99.5%)
            if (b["current_fill"] >= 99.5 or (b["current_fill"] + fill_delta) >= 99.5) and self.config["AUTO_RESET_ON_FULL"]:
                logger.info(f"Bin {b['bin_id']} reached 100% capacity! Simulating emptying collection.")
                new_fill = round(random.uniform(5.0, 10.0), 1)
            else:
                # Add Gaussian sensor bounce noise
                noise = random.gauss(0.0, self.config["NOISE_STD_DEV"])

                # Occasional sensor noise spike (e.g. temporary sensor obstruction)
                if random.random() < self.config["NOISE_SPIKE_PROBABILITY"]:
                    spike = random.choice([-1.0, 1.0]) * self.config["NOISE_SPIKE_MAGNITUDE"]
                    noise += spike

                new_fill = b["current_fill"] + fill_delta + noise
                # Clamp fill level strictly between 0.0% and 100.0%
                new_fill = max(0.0, min(100.0, new_fill))

                if new_fill >= 99.5 and self.config["AUTO_RESET_ON_FULL"]:
                    logger.info(f"Bin {b['bin_id']} reached 100% capacity! Simulating emptying collection.")
                    new_fill = round(random.uniform(5.0, 10.0), 1)

            b["current_fill"] = round(new_fill, 2)

            readings.append({
                "bin_id": b["bin_id"],
                "location_name": b.get("location_name", "VIT Campus"),
                "fill_level": b["current_fill"],
                "latitude": round(float(b["latitude"]), 6),
                "longitude": round(float(b["longitude"]), 6),
                "timestamp": now_ms
            })

        return readings

    def format_payload(self, readings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Construct the standard API Gateway ingestion payload."""
        return {"readings": readings}

    def send_readings(
        self,
        readings: List[Dict[str, Any]],
        session: Optional[requests.Session] = None
    ) -> Tuple[bool, Optional[int], Any]:
        """
        Transmit telemetry batch to the ingestion endpoint via HTTP POST.
        Handles network errors, connection timeouts, and server errors gracefully.
        Returns: (success: bool, status_code: Optional[int], response_data: Any)
        """
        payload = self.format_payload(readings)
        url = self.config["API_ENDPOINT"]

        headers = {
            "Content-Type": "application/json"
        }
        if self.config.get("API_AUTH_TOKEN"):
            headers["Authorization"] = f"Bearer {self.config['API_AUTH_TOKEN']}"

        client = session or requests

        try:
            response = client.post(
                url,
                json=payload,
                headers=headers,
                timeout=5.0
            )
            status_code = response.status_code

            try:
                resp_json = response.json()
            except Exception:
                resp_json = {"raw": response.text}

            if 200 <= status_code < 300:
                logger.info(f"Successfully posted {len(readings)} readings to {url} (HTTP {status_code}).")
                return True, status_code, resp_json
            else:
                logger.warning(f"Ingestion API returned error status {status_code}: {resp_json}")
                return False, status_code, resp_json

        except requests.ConnectionError as ce:
            logger.error(f"Connection error reaching {url}: {ce}")
            return False, None, {"error": "ConnectionError", "details": str(ce)}
        except requests.Timeout as te:
            logger.error(f"Request to {url} timed out: {te}")
            return False, None, {"error": "Timeout", "details": str(te)}
        except requests.RequestException as re:
            logger.error(f"HTTP request failed: {re}")
            return False, None, {"error": "RequestException", "details": str(re)}

    def run(
        self,
        max_ticks: Optional[int] = None,
        interval_seconds: Optional[float] = None,
        dry_run: bool = False
    ) -> int:
        """
        Run the simulation loop.
        - max_ticks: Number of iterations to run (None for indefinite continuous loop).
        - interval_seconds: Sleep interval between ticks.
        - dry_run: If True, prints telemetry to stdout without sending HTTP requests.
        Returns total ticks completed.
        """
        interval = interval_seconds if interval_seconds is not None else self.config["INTERVAL_SECONDS"]
        tick_count = 0

        logger.info(f"Starting simulation run (interval={interval}s, max_ticks={max_ticks}, dry_run={dry_run})...")

        try:
            while max_ticks is None or tick_count < max_ticks:
                readings = self.tick(delta_seconds=interval)
                tick_count += 1

                if dry_run:
                    logger.info(f"[Dry-Run Tick {tick_count}] Generated {len(readings)} readings:")
                    for r in readings[:3]:
                        logger.info(f"  {r['bin_id']} ({r['location_name']}): {r['fill_level']}%")
                    if len(readings) > 3:
                        logger.info(f"  ... and {len(readings) - 3} more bins.")
                else:
                    self.send_readings(readings)

                # Sleep only if not the final tick of a finite run
                if max_ticks is None or tick_count < max_ticks:
                    time.sleep(interval)

        except KeyboardInterrupt:
            logger.info("Simulation halted by user (KeyboardInterrupt).")

        logger.info(f"Simulation completed {tick_count} ticks.")
        return tick_count

def main():
    """Command-line entrypoint for manual simulator execution."""
    import argparse
    parser = argparse.ArgumentParser(description="IoT Waste Bin Telemetry Simulator (VIT Vellore)")
    parser.add_argument("--ticks", type=int, default=None, help="Number of ticks to execute (default: infinite)")
    parser.add_argument("--interval", type=float, default=None, help="Seconds between ticks (default from config: 10s)")
    parser.add_argument("--endpoint", type=str, default=None, help="Override ingestion API URL")
    parser.add_argument("--dry-run", action="store_true", help="Print telemetry without sending HTTP POST")

    args = parser.parse_args()

    custom_config = None
    if args.endpoint:
        custom_config = get_simulator_config()
        custom_config["API_ENDPOINT"] = args.endpoint

    sim = WasteBinSimulator(config=custom_config)
    sim.run(max_ticks=args.ticks, interval_seconds=args.interval, dry_run=args.dry_run)

if __name__ == "__main__":
    main()

