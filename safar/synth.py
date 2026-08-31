"""Synthetic dataset generator — bootstrap + eval, NOT LLM fine-tuning.

Per the data-role split (readme "Data sources"): synthetic data is the only
"training/bootstrap" bucket, used for cold-start defaults and the eval golden
trips — never to fine-tune the frontier LLM. Deterministic (seeded) so runs are
reproducible.
"""
import json
import pathlib
import random

_OUT = pathlib.Path(__file__).resolve().parents[1] / "data" / "synthetic_trips.json"

_DESTS = ["Tokyo", "Paris", "Dubai", "Singapore", "Bangkok", "Bali"]
_INTERESTS = ["food", "culture", "art", "city", "nature", "shopping"]
_PACES = ["relaxed", "moderate", "packed"]


def generate(n: int = 20, seed: int = 42) -> list[dict]:
    rng = random.Random(seed)
    trips = []
    for _ in range(n):
        interests = rng.sample(_INTERESTS, rng.randint(1, 3))
        trips.append({
            "destination": rng.choice(_DESTS),
            "days": rng.randint(3, 12),
            "budget_inr": rng.choice([90000, 150000, 200000, 300000]),
            "interests": interests,
            "pace": rng.choice(_PACES),
            "travel_month": rng.randint(1, 12),
        })
    return trips


def save(n: int = 20, seed: int = 42) -> pathlib.Path:
    _OUT.write_text(json.dumps(generate(n, seed), indent=2), encoding="utf-8")
    return _OUT


if __name__ == "__main__":
    p = save()
    print(f"wrote {p}")
