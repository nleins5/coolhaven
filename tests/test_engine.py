from dataclasses import replace

import numpy as np
import pytest

from coolhaven.data import synthetic_city
from coolhaven.engine import Config, evolve, exact_frontier, greedy, random_search, repair
from coolhaven.model import Problem
from coolhaven.pareto import dominates, hypervolume


def test_repair_handles_random_cardinality_and_tight_budget():
    city = synthetic_city()
    k = 5
    budget = sum(sorted(s.cost for s in city.sites)[:k])
    problem = Problem(city, k, budget)
    rng = np.random.default_rng(81)
    for _ in range(300):
        raw = tuple(map(int, rng.integers(0, 2, len(city.sites))))
        assert problem.feasible(repair(raw, problem, rng))


def test_full_chromosome_and_zero_generation_edge_cases(tiny_city):
    problem = Problem(tiny_city, 4, 4, 2)
    run = evolve(problem, Config(5, 0))
    assert run.evaluation_calls == 5
    assert len(run.archive) == 1
    assert run.archive[0].genome == (1, 1, 1, 1)


def test_odd_population_and_archive_hypervolume_never_regresses(tiny):
    config = Config(population=7, generations=12, seed=12)
    run = evolve(tiny, config)
    assert run.evaluation_calls == 7 * 13
    assert len(run.history) == 13
    volumes = [h["hypervolume"] for h in run.history]
    assert all(b >= a - 1e-12 for a, b in zip(volumes[:-1], volumes[1:], strict=True))
    assert all(tiny.feasible(c.genome) for c in run.archive)
    assert not any(dominates(a.objectives, b.objectives) for a in run.archive for b in run.archive)


def test_genetic_solver_recovers_small_instance_exact_frontier(tiny, tiny_city):
    run = evolve(tiny, Config(20, 15, seed=2))
    exact = exact_frontier(Problem(tiny_city, 2, 3, 2))
    assert {c.objectives for c in run.archive} == {c.objectives for c in exact.archive}
    assert hypervolume([c.objectives for c in exact.archive]) == pytest.approx(1 / 3)


def test_reproducibility(tiny_city):
    config = Config(12, 10, seed=93)
    a = evolve(Problem(tiny_city, 2, 3, 2), config)
    b = evolve(Problem(tiny_city, 2, 3, 2), config)
    assert a == b


def test_searches_get_equal_scoring_budgets(tiny_city):
    config = Config(8, 4)
    genetic = evolve(Problem(tiny_city, 2, 3, 2), config)
    random = random_search(
        Problem(tiny_city, 2, 3, 2), config.population * (config.generations + 1)
    )
    assert genetic.evaluation_calls == random.evaluation_calls == 40
    assert random.unique_evaluations <= random.evaluation_calls


def test_greedy_can_complete_at_the_minimum_budget(tiny_city):
    sites = tuple(
        replace(s, cost=cost) for s, cost in zip(tiny_city.sites, [1, 2, 8, 9], strict=True)
    )
    problem = Problem(replace(tiny_city, sites=sites), 2, 3, 2)
    candidate, calls = greedy(problem)
    assert candidate.genome == (1, 1, 0, 0)
    assert problem.feasible(candidate.genome)
    assert calls > 0


def test_exact_enumeration_has_a_size_guard():
    with pytest.raises(ValueError, match="small instances"):
        exact_frontier(Problem(synthetic_city()), max_combinations=10)


@pytest.mark.parametrize(
    "config", [Config(2, 3), Config(4, -1), Config(4, 1, mutation_rate=1.1), Config(4, 1, seed=-1)]
)
def test_bad_solver_config(config):
    with pytest.raises(ValueError):
        config.validate()
