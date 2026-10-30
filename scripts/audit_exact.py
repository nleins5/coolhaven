"""Audit the default instance against all 24-choose-5 candidate combinations."""

import csv
import json
from math import comb
from pathlib import Path

from coolhaven.cli import candidate_dict
from coolhaven.engine import exact_frontier
from coolhaven.model import Problem, load_city
from coolhaven.pareto import hypervolume

root = Path(__file__).resolve().parents[1]
problem = Problem(load_city(root / "data/synthetic_city.json"))
run = exact_frontier(problem)
volume = hypervolume([c.objectives for c in run.archive])
with (root / "results/benchmark.csv").open() as stream:
    benchmark = list(csv.DictReader(stream))
gaps = [
    {
        "seed": int(r["seed"]),
        "hypervolume": float(r["hypervolume"]),
        "relative_hv_gap": 1 - float(r["hypervolume"]) / volume,
    }
    for r in benchmark
    if r["algorithm"] == "NSGA-II"
]
report = {
    "fixture": "data/synthetic_city.json",
    "hubs": 5,
    "budget": 210,
    "radius": 2.4,
    "total_combinations": comb(len(problem.city.sites), problem.hubs),
    "feasible_combinations": run.evaluation_calls,
    "exact_frontier_size": len(run.archive),
    "exact_hypervolume": volume,
    "reference": [1, 1, 1],
    "nsga_runs": gaps,
    "frontier": [candidate_dict(c, problem) for c in run.archive],
}
(root / "results/exact_audit.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps({k: v for k, v in report.items() if k != "frontier"}, indent=2))
