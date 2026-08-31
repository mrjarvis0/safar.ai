"""NVIDIA Earth-2 FourCastNet — AI global weather forecast (weather grounding, §11).

FourCastNet is NVIDIA's data-driven global weather model. It ships as a
SELF-HOSTED NIM container (GPU) — NOT a hosted API on integrate.api.nvidia.com.
Deploy it (https://docs.nvidia.com/nim/earth-2/fourcastnet) and point
FOURCASTNET_URL at it (e.g. http://localhost:8000). Safar then grounds its
weather on FourCastNet's medium-range forecast; when the NIM is not deployed or
unreachable it degrades gracefully and Safar falls back to Open-Meteo. Every call
is guarded (short timeout + try/except) like the rest of the gateway, so a missing
NIM never breaks a plan.

Real NIM contract — POST /v1/infer (multipart/form-data):
  input_array=@fcn_inputs.npy   73-channel global initial condition (721x1440),
                                built with Earth2Studio from ARCO ERA5.
  input_time=2023-01-01T00:00:00Z
  simulation_length=<N>         forecast steps (6h each).
Response: a tar archive of .npy arrays, one per forecast step.
Health:  GET /v1/health/ready
"""
import io
import tarfile

import requests

from .. import config

_HEALTH_TIMEOUT = 3      # keep planning fast even if a configured NIM is down
_INFER_TIMEOUT = 120     # inference is heavy (global grid)

# FourCastNet grid: 0.25° regular lat/lon, 721x1440 (lat 90..-90, lon 0..359.75).
_NLAT, _NLON = 721, 1440


def _base() -> str:
    return (config.FOURCASTNET_URL or "").rstrip("/")


def _headers() -> dict:
    key = config.FOURCASTNET_API_KEY
    return {"Authorization": f"Bearer {key}"} if key else {}


def status() -> dict:
    """Whether a FourCastNet NIM is configured and reachable.

    Mirrors gateway.gtfs_status(): {configured, url, reachable, note}. When no URL
    is set it returns immediately (no network), so the default demo adds zero
    latency. Never raises.
    """
    url = _base()
    if not url:
        return {"configured": False, "url": None, "reachable": False,
                "note": "Set FOURCASTNET_URL to a deployed NIM "
                        "(e.g. http://localhost:8000) to enable AI forecasts."}
    try:
        r = requests.get(f"{url}/v1/health/ready", headers=_headers(),
                         timeout=_HEALTH_TIMEOUT)
        reachable = r.ok
    except Exception:
        reachable = False
    return {"configured": True, "url": url, "reachable": reachable,
            "note": None if reachable else "NIM configured but not reachable."}


def infer(input_array_path: str, input_time: str,
          simulation_length: int = 4) -> bytes | None:
    """POST an initial-condition .npy to /v1/infer; return the raw tar bytes.

    Returns None when no NIM is configured or the call fails (caller falls back).
    `input_array_path` is a .npy built with Earth2Studio from ERA5.
    """
    url = _base()
    if not url:
        return None
    try:
        with open(input_array_path, "rb") as f:
            r = requests.post(
                f"{url}/v1/infer",
                headers=_headers(),
                files={"input_array": f},
                data={"input_time": input_time,
                      "simulation_length": str(int(simulation_length))},
                timeout=_INFER_TIMEOUT)
        r.raise_for_status()
        return r.content
    except Exception:
        return None


def forecast_steps(tar_bytes: bytes) -> list:
    """Parse the /v1/infer tar into a list of NumPy arrays (one per step).

    Requires numpy (optional dependency — only needed once a NIM is deployed).
    Returns [] if numpy is missing or parsing fails.
    """
    if not tar_bytes:
        return []
    try:
        import numpy as np
    except Exception:
        return []
    out = []
    try:
        with tarfile.open(fileobj=io.BytesIO(tar_bytes)) as tf:
            for m in sorted(tf.getmembers(), key=lambda x: x.name):
                if m.name.endswith(".npy"):
                    fh = tf.extractfile(m)
                    if fh is not None:
                        out.append(np.load(io.BytesIO(fh.read())))
    except Exception:
        return []
    return out


def sample_point(step_array, lat: float, lon: float, channel: int = 0):
    """Nearest-cell sample from one forecast step for a given channel.

    Expects an array shaped (channels, 721, 1440) — or (721, 1440) for a single
    channel. The channel index maps to a physical variable per the NIM's channel
    order (see the FourCastNet docs). Returns a float, or None on any error.
    """
    try:
        i = int(round((90.0 - lat) / 180.0 * (_NLAT - 1)))
        j = int(round((lon % 360.0) / 360.0 * _NLON)) % _NLON
        i = min(max(i, 0), _NLAT - 1)
        arr = step_array[channel] if getattr(step_array, "ndim", 2) == 3 else step_array
        return float(arr[i, j])
    except Exception:
        return None


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print("NVIDIA FourCastNet NIM —", status())
