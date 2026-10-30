"""Compare outage-aware and outage-blind planning on the same stress evaluator.

Run from the repository root: uv run python scripts/ablation.py
"""

import csv
import json
import statistics
from dataclasses import replace
from pathlib import Path

from coolhaven.engine import Config, evolve
from coolhaven.model import Problem, load_city
from coolhaven.pareto import compromise

root = Path(__file__).resolve().parents[1]
city = load_city(root / "data/synthetic_city.json")
no_closures = replace(city, scenarios=tuple(s for s in city.scenarios if not s.unavailable))
rows = []
for seed in (11, 23, 42, 71, 97):
    for label, planning_city in (("Outage-aware", city), ("Without outage scenarios", no_closures)):
        run = evolve(Problem(planning_city), Config(seed=seed))
        chosen = compromise(run.archive)
        # Select using the planning model before stress scoring with the full model.
        stressed = Problem(city).evaluate(chosen.genome).metrics
        rows.append(
            {
                "seed": seed,
                "planning_model": label,
                "stressed_robust_access": stressed.robust_access,
                "stressed_worst_group_access": stressed.equitable_access,
                "cost": stressed.cost,
                "planning_evaluation_calls": run.evaluation_calls,
            }
        )
with (root / "results/ablation.csv").open("w", newline="") as stream:
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
summary = {}
for label in ("Outage-aware", "Without outage scenarios"):
    subset = [r for r in rows if r["planning_model"] == label]
    summary[label] = {
        key: statistics.mean(r[key] for r in subset)
        for key in ("stressed_robust_access", "stressed_worst_group_access", "cost")
    }
metadata = {
    "seeds": [11, 23, 42, 71, 97],
    "config": {"population": 64, "generations": 60},
    "hubs": 5,
    "budget": 210,
    "radius": 2.4,
    "weights": [0.45, 0.4, 0.15],
    "fixture": "data/synthetic_city.json",
    "summary": summary,
    "interpretation": "Post-hoc stress scoring of a compromise chosen within each planning model. "
    "This isolates inclusion of closure scenarios, not an out-of-distribution guarantee.",
}
(root / "results/ablation_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
print(json.dumps(summary, indent=2))
