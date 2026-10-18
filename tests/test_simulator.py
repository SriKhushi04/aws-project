"""Unit tests for the IoT Waste Bin Simulator."""
import json
import pytest
from unittest.mock import patch, MagicMock
import requests

from simulator.simulate_bins import WasteBinSimulator
from lambdas.waste_ingest.lambda_function import validate_reading

def test_simulator_initialization():
    """Verify that the simulator loads 12 bins with valid coordinates around VIT Vellore."""
    sim = WasteBinSimulator()
    assert len(sim.bins) == 12

    for b in sim.bins:
        assert b["bin_id"].startswith("BIN-")
        assert 12.9600 <= b["latitude"] <= 12.9800  # VIT Vellore latitude range
        assert 79.1500 <= b["longitude"] <= 79.1700 # VIT Vellore longitude range
        assert 0.0 <= b["initial_fill"] <= 100.0
        assert b["fill_rate_per_hour"] > 0

def test_tick_advancement_and_bounds():
    """Verify that tick increments fill levels and clamps to [0, 100]."""
    custom_bins = [
        {"bin_id": "BIN-TEST", "latitude": 12.9698, "longitude": 79.1559, "initial_fill": 50.0, "fill_rate_per_hour": 10.0}
    ]
    sim = WasteBinSimulator(custom_bins=custom_bins)
    readings = sim.tick(delta_seconds=360.0)  # 6 minutes

    assert len(readings) == 1
    r = readings[0]
    assert r["bin_id"] == "BIN-TEST"
    assert 0.0 <= r["fill_level"] <= 100.0
    assert r["timestamp"] > 0
    # Expected base increase: (10.0 * 360) / 3600 = 1.0% plus/minus noise
    assert 48.0 <= r["fill_level"] <= 55.0

def test_auto_reset_on_full():
    """Verify that a full bin (>= 99.5%) automatically resets to baseline (5-10%)."""
    custom_bins = [
        {"bin_id": "BIN-FULL", "latitude": 12.9698, "longitude": 79.1559, "initial_fill": 99.8, "fill_rate_per_hour": 10.0}
    ]
    sim = WasteBinSimulator(custom_bins=custom_bins)
    readings = sim.tick(delta_seconds=10.0)

    # Bin should have triggered collection reset
    assert len(readings) == 1
    assert 5.0 <= readings[0]["fill_level"] <= 15.0

def test_payload_format_matches_ingest_contract():
    """Verify that the generated payload strictly passes waste-ingest validation rules."""
    sim = WasteBinSimulator()
    readings = sim.tick(delta_seconds=10.0)
    payload = sim.format_payload(readings)

    assert "readings" in payload
    assert len(payload["readings"]) == 12

    # Verify each reading passes waste-ingest schema validator
    for idx, r in enumerate(payload["readings"]):
        cleaned = validate_reading(r, idx)
        assert cleaned["bin_id"] == r["bin_id"]
        assert cleaned["fill_level"] == r["fill_level"]
        assert cleaned["latitude"] == r["latitude"]
        assert cleaned["longitude"] == r["longitude"]

@patch("requests.post")
def test_send_readings_success(mock_post):
    """Verify successful HTTP POST transmission."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "success", "ingested_count": 12}
    mock_post.return_value = mock_resp

    sim = WasteBinSimulator()
    readings = sim.tick(delta_seconds=10.0)
    success, status_code, data = sim.send_readings(readings)

    assert success is True
    assert status_code == 200
    assert data["status"] == "success"
    mock_post.assert_called_once()

@patch("requests.post")
def test_send_readings_api_error(mock_post):
    """Verify handling of HTTP 400 Bad Request."""
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.json.return_value = {"status": "error", "message": "Validation failed"}
    mock_post.return_value = mock_resp

    sim = WasteBinSimulator()
    readings = sim.tick(delta_seconds=10.0)
    success, status_code, data = sim.send_readings(readings)

    assert success is False
    assert status_code == 400
    assert data["status"] == "error"

@patch("requests.post")
def test_send_readings_network_exception(mock_post):
    """Verify graceful handling of ConnectionError without crashing."""
    mock_post.side_effect = requests.ConnectionError("Failed to establish connection")

    sim = WasteBinSimulator()
    readings = sim.tick(delta_seconds=10.0)
    success, status_code, data = sim.send_readings(readings)

    assert success is False
    assert status_code is None
    assert data["error"] == "ConnectionError"

def test_finite_run_mode():
    """Verify that run() with max_ticks completes cleanly in finite mode."""
    sim = WasteBinSimulator()
    with patch.object(sim, "send_readings", return_value=(True, 200, {})):
        completed_ticks = sim.run(max_ticks=3, interval_seconds=0.001)
        assert completed_ticks == 3

