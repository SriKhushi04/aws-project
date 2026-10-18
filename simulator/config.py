"""Configuration for the IoT Waste Bin Simulator."""
import os

def _load_dotenv_if_present():
    """Load key-value pairs from .env in project root if present and not already set."""
    env_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
    if os.path.isfile(env_file):
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("'\"")
                    if key and key not in os.environ:
                        os.environ[key] = val
        except Exception:
            pass

_load_dotenv_if_present()

def get_env(name: str, default: str = "") -> str:
    """Retrieve an environment variable safely."""
    return os.environ.get(name, default).strip()

def get_simulator_config() -> dict:
    """Load simulator configuration from environment variables with fallbacks."""
    api_endpoint = get_env(
        "SIMULATOR_API_ENDPOINT",
        get_env("API_GATEWAY_URL", "http://localhost:8000") + "/readings"
    )
    # Ensure URL doesn't have duplicate slashes
    if api_endpoint.endswith("/readings/readings"):
        api_endpoint = api_endpoint.replace("/readings/readings", "/readings")

    return {
        "API_ENDPOINT": api_endpoint,
        "API_AUTH_TOKEN": get_env("API_AUTH_TOKEN", ""),
        "INTERVAL_SECONDS": float(get_env("SIMULATOR_INTERVAL_SECONDS", "10.0")),
        "NOISE_STD_DEV": float(get_env("SIMULATOR_NOISE_STD", "0.5")),
        "NOISE_SPIKE_PROBABILITY": float(get_env("SIMULATOR_SPIKE_PROB", "0.05")),
        "NOISE_SPIKE_MAGNITUDE": float(get_env("SIMULATOR_SPIKE_MAGNITUDE", "2.5")),
        "AUTO_RESET_ON_FULL": get_env("SIMULATOR_AUTO_RESET", "true").lower() in ("true", "1", "yes"),
        "DEPOT_COORDINATES": {
            "name": "VIT Estates & Maintenance Depot",
            "latitude": float(get_env("DEPOT_LATITUDE", "12.9685")),
            "longitude": float(get_env("DEPOT_LONGITUDE", "79.1550"))
        }
    }

