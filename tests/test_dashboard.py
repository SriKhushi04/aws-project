"""Unit tests and structural validation for the Leaflet Web Dashboard frontend."""
import os
import re
import pytest

DASHBOARD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "dashboard"))

def test_dashboard_files_exist():
    """Verify that all required frontend assets are present."""
    required_files = [
        "index.html",
        os.path.join("css", "styles.css"),
        os.path.join("js", "config.js"),
        os.path.join("js", "map.js"),
        os.path.join("js", "app.js")
    ]
    for rel_path in required_files:
        full_path = os.path.join(DASHBOARD_DIR, rel_path)
        assert os.path.isfile(full_path), f"Missing dashboard file: {rel_path}"

def test_index_html_structure():
    """Verify index.html contains necessary DOM containers, Leaflet CDN, and script tags."""
    index_path = os.path.join(DASHBOARD_DIR, "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        html = f.read()

    # Verify Leaflet CDN resources
    assert "unpkg.com/leaflet" in html
    assert "leaflet.css" in html
    assert "leaflet.js" in html

    # Verify key DOM elements required by app.js
    required_ids = [
        "map",
        "stat-total-bins",
        "stat-critical-bins",
        "stat-avg-fill",
        "stat-route-distance",
        "route-stops-list",
        "bins-inventory-list",
        "system-banner",
        "conn-dot",
        "btn-refresh"
    ]
    for element_id in required_ids:
        assert f'id="{element_id}"' in html, f"Missing DOM element with id '{element_id}'"

    # Verify script includes
    assert '<script src="js/config.js"></script>' in html
    assert '<script src="js/map.js"></script>' in html
    assert '<script src="js/app.js"></script>' in html

def test_css_styles():
    """Verify CSS defines status indicators, responsive layout, and animations."""
    css_path = os.path.join(DASHBOARD_DIR, "css", "styles.css")
    with open(css_path, "r", encoding="utf-8") as f:
        css = f.read()

    assert "--status-normal" in css
    assert "--status-warning" in css
    assert "--status-critical" in css
    assert "pulse-red" in css  # Pulsing animation for critical bins
    assert "@media" in css     # Mobile responsive rules

def test_config_js_settings():
    """Verify config.js defines map center around VIT Vellore and threshold values."""
    config_path = os.path.join(DASHBOARD_DIR, "js", "config.js")
    with open(config_path, "r", encoding="utf-8") as f:
        js = f.read()

    assert "window.API_CONFIG" in js
    assert "mapCenter" in js
    assert "12.97" in js  # VIT Vellore latitude coordinate
    assert "79.15" in js  # VIT Vellore longitude coordinate
    assert "warning: 50.0" in js or "warning: 50" in js
    assert "critical: 85.0" in js or "critical: 85" in js

def test_map_js_functions():
    """Verify map.js implements core rendering functions and stable marker caching."""
    map_path = os.path.join(DASHBOARD_DIR, "js", "map.js")
    with open(map_path, "r", encoding="utf-8") as f:
        js = f.read()

    assert "function initMap(" in js
    assert "function renderBins(" in js
    assert "function renderRoute(" in js
    assert "L.circleMarker" in js
    assert "L.polyline" in js
    assert "binMarkersMap" in js
    assert "setLatLng" in js
    assert "setStyle" in js

def test_app_js_compatibility():
    """Verify app.js matches the REST contract of waste_api."""
    app_path = os.path.join(DASHBOARD_DIR, "js", "app.js")
    with open(app_path, "r", encoding="utf-8") as f:
        js = f.read()

    # Verify endpoint paths
    assert "/bins" in js
    assert "/route" in js

    # Verify consumption of fields produced by waste-api & waste-analytics
    assert "fill_level" in js
    assert "bin_id" in js
    assert "total_distance_km" in js
    assert "stops" in js
    assert "predicted_hours_to_90" in js

