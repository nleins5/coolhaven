"""Seeded synthetic city; coordinates are local schematic kilometers."""

from __future__ import annotations

import numpy as np

from coolhaven.model import City, Demand, Scenario, Site


def synthetic_city(seed: int = 17, outages: bool = True) -> City:
    rng = np.random.default_rng(seed)
    groups = ("Westbank", "Old Quarter", "Eastbank", "Garden", "Market", "Riverside")
    demand, sites = [], []
    for g, name in enumerate(groups):
        cx, cy = 0.8 + (g % 3) * 1.7, 0.8 + (g // 3) * 1.8
        for j in range(12):
            x, y = np.clip(rng.normal([cx, cy], [0.42, 0.42]), [0.1, 0.1], [5.6, 3.9])
            demand.append(
                Demand(
                    f"D{g * 12 + j + 1:02}",
                    name,
                    round(float(x), 3),
                    round(float(y), 3),
                    int(rng.integers(150, 701)),
                    round(float(rng.uniform(0.15, 0.95)), 3),
                    round(float(rng.uniform(0.9, 1.4) + (0.2 if g in (1, 5) else 0)), 3),
                )
            )
        for j in range(4):
            x, y = rng.normal([cx, cy], [0.5, 0.5])
            sites.append(
                Site(
                    f"H{g * 4 + j + 1:02}",
                    f"{name} · {j + 1}",
                    round(float(np.clip(x, 0.1, 5.6)), 3),
                    round(float(np.clip(y, 0.1, 3.9)), 3),
                    float(rng.integers(24, 59)),
                )
            )
    scenarios = [Scenario("normal", 1.0), Scenario("heatwave", 1.25)]
    if outages:
        scenarios.extend(Scenario(f"heatwave_without_{s.id}", 1.25, (s.id,)) for s in sites)
    return City(
        "Six Neighbourhoods",
        f"Synthetic teaching fixture, NumPy PCG64 seed {seed}; no real locations or observations.",
        tuple(demand),
        tuple(sites),
        tuple(scenarios),
    )
