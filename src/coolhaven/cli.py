"""Reproduce optimization and equal-budget experiments without the dashboard."""

from __future__ import annotations

import argparse
import csv
import json
import platform
import statistics
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np

from coolhaven import __version__
from coolhaven.data import synthetic_city
from coolhaven.engine import Config, evolve, greedy, random_search
from coolhaven.model import Problem, load_city
from coolhaven.pareto import compromise, hypervolume


def candidate_dict(candidate, problem):
    return {
        "selected_sites": [
            s.id for s, bit in zip(problem.city.sites, candidate.genome, strict=True) if bit
        ],
        "genome": candidate.genome,
        "objectives": candidate.objectives,
        "metrics": asdict(candidate.metrics),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["solve", "benchmark", "generate"])
    parser.add_argument("--data", type=Path)
    parser.add_argument("--out", type=Path, default=Path("results"))
    parser.add_argument("--hubs", type=int, default=5)
    parser.add_argument("--budget", type=float, default=210)
    parser.add_argument("--radius", type=float, default=2.4)
    parser.add_argument("--population", type=int, default=64)
    parser.add_argument("--generations", type=int, default=60)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--seeds", type=int, nargs="+", default=[11, 23, 42, 71, 97])
    args = parser.parse_args(argv)
    city = load_city(args.data) if args.data else synthetic_city()
    args.out.mkdir(parents=True, exist_ok=True)
    if args.command == "generate":
        target = args.out / "synthetic_city.json"
        target.write_text(json.dumps(city.to_dict(), indent=2) + "\n")
        print(target)
        return

    def make_problem():
        return Problem(city, args.hubs, args.budget, args.radius)

    config = Config(args.population, args.generations, seed=args.seed)
    config.validate()
    if args.command == "solve":
        problem = make_problem()
        run = evolve(problem, config)
        output = {
            "config": asdict(config),
            "hubs": args.hubs,
            "budget": args.budget,
            "radius": args.radius,
            "city": city.to_dict(),
            "recommended": candidate_dict(compromise(run.archive), problem),
            "frontier": [candidate_dict(c, problem) for c in run.archive],
            "history": run.history,
            "evaluation_calls": run.evaluation_calls,
            "unique_evaluations": run.unique_evaluations,
        }
        (args.out / "solution.json").write_text(json.dumps(output, indent=2) + "\n")
        print(json.dumps(output["recommended"], indent=2))
        return

    rows = []
    evaluation_budget = args.population * (args.generations + 1)
    for seed in args.seeds:
        for algorithm in ("NSGA-II", "Random search", "Greedy"):
            problem = make_problem()
            started = time.perf_counter()
            if algorithm == "NSGA-II":
                run = evolve(problem, Config(args.population, args.generations, seed=seed))
                candidates, calls, unique = (
                    run.archive,
                    run.evaluation_calls,
                    run.unique_evaluations,
                )
            elif algorithm == "Random search":
                run = random_search(problem, evaluation_budget, seed)
                candidates, calls, unique = (
                    run.archive,
                    run.evaluation_calls,
                    run.unique_evaluations,
                )
            else:
                candidate, calls = greedy(problem)
                candidates, unique = [candidate], calls
            seconds = time.perf_counter() - started
            chosen = compromise(candidates)
            row = {
                "seed": seed,
                "algorithm": algorithm,
                "hypervolume": hypervolume([c.objectives for c in candidates]),
                "robust_access": chosen.metrics.robust_access,
                "equitable_access": chosen.metrics.equitable_access,
                "cost": chosen.metrics.cost,
                "frontier_size": len(candidates),
                "evaluation_calls": calls,
                "unique_evaluations": unique,
                "seconds": seconds,
            }
            rows.append(row)
            print(f"{algorithm:14} seed={seed:3} HV={row['hypervolume']:.6f} ({seconds:.2f}s)")
    with (args.out / "benchmark.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    metadata = {
        "coolhaven_version": __version__,
        "python": platform.python_version(),
        "numpy": np.__version__,
        "platform": platform.platform(),
        "population": args.population,
        "generations": args.generations,
        "evaluation_budget": evaluation_budget,
        "seeds": args.seeds,
        "hubs": args.hubs,
        "budget": args.budget,
        "radius": args.radius,
        "preference_weights": [0.45, 0.4, 0.15],
        "hypervolume_reference": [1, 1, 1],
        "scenario": city.to_dict(),
        "greedy_note": "Deterministic; repeated across seeds for table alignment only. "
        "Partial-set scoring calls are included; it does not consume the equal search budget.",
    }
    (args.out / "benchmark_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    lines = [
        "# Benchmark results",
        "",
        "Synthetic city; five hubs, explicit stress scenarios. "
        "Scores measure model accessibility, not real-world health outcomes.",
        "",
        "| Method | Hypervolume mean ± sample SD | Robust access mean | Worst-group mean |",
        "|---|---:|---:|---:|",
    ]
    for algorithm in ("NSGA-II", "Random search", "Greedy"):
        subset = [r for r in rows if r["algorithm"] == algorithm]
        hv = [r["hypervolume"] for r in subset]
        deviation = statistics.stdev(hv) if len(hv) > 1 else 0
        lines.append(
            f"| {algorithm} | {statistics.mean(hv):.6f} ± {deviation:.6f} | "
            f"{statistics.mean(r['robust_access'] for r in subset):.3%} | "
            f"{statistics.mean(r['equitable_access'] for r in subset):.3%} |"
        )
    lines += [
        "",
        f"NSGA-II and random search each use **{evaluation_budget:,} candidate scoring "
        "calls per seed**, including duplicates. Unique counts are reported in the CSV.",
        "",
        "Hypervolume compares complete returned frontiers. Access columns describe "
        "one post-hoc compromise with fixed preference weights (0.45, 0.40, 0.15). "
        "They need not improve together. Greedy is deterministic and uses fewer calls. "
        "These runs do not establish statistical significance or general superiority.",
        "",
    ]
    (args.out / "REPORT.md").write_text("\n".join(lines))


if __name__ == "__main__":
    main()
