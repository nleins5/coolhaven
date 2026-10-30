"""A compact NSGA-II: binary chromosomes, hard repair and an external archive."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from math import comb

import numpy as np

from coolhaven.model import Candidate, Genome, Problem
from coolhaven.pareto import crowding, frontier, hypervolume, sort_fronts


@dataclass(frozen=True)
class Config:
    population: int = 64
    generations: int = 60
    crossover_rate: float = 0.9
    mutation_rate: float = 0.35
    seed: int = 42

    def validate(self):
        if not isinstance(self.population, int) or self.population < 4:
            raise ValueError("Population must be an integer of at least 4.")
        if not isinstance(self.generations, int) or self.generations < 0:
            raise ValueError("Generations must be a nonnegative integer.")
        if not 0 <= self.crossover_rate <= 1 or not 0 <= self.mutation_rate <= 1:
            raise ValueError("Operator probabilities must be in [0, 1].")
        if not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError("Seed must be a nonnegative integer.")


@dataclass
class Run:
    archive: list[Candidate]
    history: list[dict]
    evaluation_calls: int
    unique_evaluations: int


def repair(genome: Genome, problem: Problem, rng: np.random.Generator) -> Genome:
    """Restore cardinality, then replace expensive sites until the budget holds.

    Feasibility follows because each budget swap strictly reduces cost, and the
    cheapest k-set is affordable. The repair introduces a documented cheap-site bias.
    """
    if len(genome) != len(problem.costs) or any(bit not in (0, 1) for bit in genome):
        raise ValueError("Repair expects a binary chromosome of the correct length.")
    bits = np.array(genome, dtype=int)
    selected = np.flatnonzero(bits)
    if len(selected) > problem.hubs:
        bits[rng.choice(selected, len(selected) - problem.hubs, replace=False)] = 0
    elif len(selected) < problem.hubs:
        bits[rng.choice(np.flatnonzero(bits == 0), problem.hubs - len(selected), replace=False)] = 1
    while float(problem.costs @ bits) > problem.budget + 1e-9:
        selected, absent = np.flatnonzero(bits), np.flatnonzero(bits == 0)
        remove = selected[np.argmax(problem.costs[selected])]
        add = absent[np.argmin(problem.costs[absent])]
        if problem.costs[remove] <= problem.costs[add]:
            raise RuntimeError("Feasibility invariant violated during budget repair.")
        bits[remove], bits[add] = 0, 1
    return tuple(map(int, bits))


def random_genome(problem: Problem, rng: np.random.Generator) -> Genome:
    bits = np.zeros(len(problem.costs), dtype=int)
    bits[rng.choice(len(bits), problem.hubs, replace=False)] = 1
    return repair(tuple(map(int, bits)), problem, rng)


def offspring(a: Genome, b: Genome, problem: Problem, rng, config: Config) -> Genome:
    bits = np.array(a, dtype=int)
    if rng.random() < config.crossover_rate:
        mask = rng.random(len(bits)) < 0.5
        bits[mask] = np.array(b)[mask]
    child = repair(tuple(map(int, bits)), problem, rng)
    if rng.random() < config.mutation_rate and problem.hubs < len(bits):
        bits = np.array(child)
        remove = rng.choice(np.flatnonzero(bits))
        add = rng.choice(np.flatnonzero(bits == 0))
        bits[remove], bits[add] = 0, 1
        child = repair(tuple(map(int, bits)), problem, rng)
    return child


def rank_and_crowding(population: list[Candidate]):
    values = np.array([c.objectives for c in population])
    ranks, distances = np.empty(len(population), dtype=int), np.zeros(len(population))
    for rank, indices in enumerate(sort_fronts(values)):
        ranks[indices] = rank
        distances[indices] = crowding(values[indices])
    return ranks, distances


def survive(candidates: list[Candidate], size: int) -> list[Candidate]:
    """Elitist parent + child selection, preserving objective-space diversity."""
    # Prefer unique genomes, retaining duplicates only when the feasible space is tiny.
    unique = list({c.genome: c for c in candidates}.values())
    pool = unique if len(unique) >= size else unique + candidates[: size - len(unique)]
    values = np.array([c.objectives for c in pool])
    selected = []
    for indices in sort_fronts(values):
        room = size - len(selected)
        if len(indices) <= room:
            selected.extend(indices)
        else:
            distances = crowding(values[indices])
            order = sorted(range(len(indices)), key=lambda j: (-distances[j], indices[j]))
            selected.extend(indices[j] for j in order[:room])
            break
    return [pool[i] for i in selected]


def evolve(problem: Problem, config: Config | None = None, progress=None) -> Run:
    config = config or Config()
    config.validate()
    rng = np.random.default_rng(config.seed)
    initial_calls, initial_unique = problem.calls, len(problem.cache)
    population = [problem.evaluate(random_genome(problem, rng)) for _ in range(config.population)]
    archive, history = [], []
    for generation in range(config.generations + 1):
        archive = frontier(archive + population)
        entry = {
            "generation": generation,
            "hypervolume": hypervolume([c.objectives for c in archive]),
            "frontier_size": len(archive),
            "diversity": len({c.genome for c in population}) / len(population),
            "best_robust_access": max(c.metrics.robust_access for c in archive),
            "best_equitable_access": max(c.metrics.equitable_access for c in archive),
            "evaluation_calls": problem.calls - initial_calls,
        }
        history.append(entry)
        if progress:
            progress(generation, config.generations)
        if generation == config.generations:
            break
        ranks, distances = rank_and_crowding(population)

        def tournament(pool=population, rank=ranks, distance=distances):
            a, b = map(int, rng.integers(0, len(pool), size=2))
            score_a, score_b = (rank[a], -distance[a]), (rank[b], -distance[b])
            if score_a == score_b:
                winner = a if rng.random() < 0.5 else b
            else:
                winner = a if score_a < score_b else b
            return pool[winner].genome

        children = [
            problem.evaluate(offspring(tournament(), tournament(), problem, rng, config))
            for _ in range(config.population)
        ]
        # Archive every evaluated child before environmental truncation.
        archive = frontier(archive + children)
        population = survive(population + children, config.population)
    return Run(archive, history, problem.calls - initial_calls, len(problem.cache) - initial_unique)


def random_search(problem: Problem, evaluations: int, seed: int = 42) -> Run:
    if not isinstance(evaluations, int) or evaluations < 1:
        raise ValueError("Evaluation budget must be a positive integer.")
    rng = np.random.default_rng(seed)
    initial_calls, initial_unique = problem.calls, len(problem.cache)
    archive = []
    # Batches bound the dominance matrix instead of sorting all samples at once.
    for start in range(0, evaluations, 128):
        batch = [
            problem.evaluate(random_genome(problem, rng))
            for _ in range(min(128, evaluations - start))
        ]
        archive = frontier(archive + batch)
    return Run(archive, [], problem.calls - initial_calls, len(problem.cache) - initial_unique)


def greedy(problem: Problem, weights=(0.45, 0.4, 0.15)) -> tuple[Candidate, int]:
    """Forward selection with a cheapest-completion feasibility lookahead.

    Partial sets use the same robust objectives. Nominal access breaks early ties
    when every one-hub plan fails the single-outage stress test.
    """
    bits = np.zeros(len(problem.costs), dtype=int)
    evaluations = 0
    for _ in range(problem.hubs):
        options = []
        for index in np.flatnonzero(bits == 0):
            trial = bits.copy()
            trial[index] = 1
            left = problem.hubs - int(trial.sum())
            completion_cost = np.sort(problem.costs[trial == 0])[:left].sum()
            if float(problem.costs @ trial + completion_cost) > problem.budget + 1e-9:
                continue
            m = problem.metrics(tuple(map(int, trial)))
            objectives = (1 - m.robust_access, 1 - m.equitable_access, m.cost / problem.budget)
            score = sum(w * v for w, v in zip(weights, objectives, strict=True))
            options.append((score, -m.nominal_access, int(index)))
            evaluations += 1
        if not options:
            raise RuntimeError("Greedy completion invariant violated.")
        bits[min(options)[2]] = 1
    return problem.evaluate(tuple(map(int, bits))), evaluations + 1


def exact_frontier(problem: Problem, max_combinations: int = 100_000) -> Run:
    n = len(problem.costs)
    if comb(n, problem.hubs) > max_combinations:
        raise ValueError("Exact enumeration is limited to small instances.")
    initial_calls, initial_unique = problem.calls, len(problem.cache)
    candidates = []
    archive = []
    for selected in combinations(range(n), problem.hubs):
        bits = tuple(int(i in selected) for i in range(n))
        if problem.feasible(bits):
            candidates.append(problem.evaluate(bits))
        if len(candidates) == 128:
            archive = frontier(archive + candidates)
            candidates = []
    archive = frontier(archive + candidates)
    return Run(archive, [], problem.calls - initial_calls, len(problem.cache) - initial_unique)
