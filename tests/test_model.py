from dataclasses import replace

import pytest

from coolhaven.data import synthetic_city
from coolhaven.model import Problem, Scenario


def test_access_has_hand_calculated_mean_and_equity(tiny):
    candidate = tiny.evaluate((1, 0, 0, 1))
    assert candidate.metrics.nominal_access == pytest.approx(0.75)
    assert candidate.metrics.robust_access == pytest.approx(0.75)
    assert candidate.metrics.equitable_access == pytest.approx(0.5)
    assert candidate.metrics.covered_population == 200
    assert candidate.objectives == pytest.approx((0.25, 0.5, 2 / 3))


def test_one_closed_hub_can_leave_a_group_with_zero_access(tiny_city):
    city = replace(tiny_city, scenarios=(Scenario("normal", 1), Scenario("outage", 1, ("A",))))
    result = Problem(city, 2, 3, 2).evaluate((1, 0, 1, 0)).metrics
    assert result.nominal_access == 1
    assert result.robust_access == 0.5
    assert result.equitable_access == 0


def test_slow_walking_reduces_access(tiny_city):
    normal = Problem(tiny_city, 2, 3, 2).evaluate((0, 1, 0, 1)).metrics
    slower_city = replace(tiny_city, scenarios=(Scenario("heat", 2),))
    slower = Problem(slower_city, 2, 3, 2).evaluate((0, 1, 0, 1)).metrics
    assert normal.robust_access == 0.5
    assert slower.robust_access == 0


@pytest.mark.parametrize("genome", [(1, 1), (2, 0, 0, 0), (1, 0, 0, 0), (1, 1, 1, 1)])
def test_invalid_genomes_are_rejected(tiny, genome):
    with pytest.raises(ValueError):
        tiny.evaluate(genome)


@pytest.mark.parametrize(
    "hubs,budget,radius",
    [
        (0, 3, 2),
        (5, 3, 2),
        (2, 1, 2),
        (2, 3, 0),
        (2, float("nan"), 2),
        (2, 3, float("inf")),
        (True, 3, 2),
    ],
)
def test_invalid_planning_constraints(tiny_city, hubs, budget, radius):
    with pytest.raises(ValueError):
        Problem(tiny_city, hubs, budget, radius)


def test_cache_tracks_calls_separately_from_unique_plans(tiny):
    first = tiny.evaluate((1, 0, 1, 0))
    second = tiny.evaluate((1, 0, 1, 0))
    assert first is second
    assert tiny.calls == 2
    assert len(tiny.cache) == 1


def test_unknown_outage_site_is_rejected(tiny_city):
    with pytest.raises(ValueError, match="unknown site"):
        replace(tiny_city, scenarios=(Scenario("oops", 1, ("missing",)),)).validate()


def test_synthetic_data_has_no_random_global_state():
    assert synthetic_city(17) == synthetic_city(17)
    assert synthetic_city(17) != synthetic_city(18)


def test_extra_stress_scenarios_cannot_improve_robust_scores():
    normal = Problem(synthetic_city(outages=False))
    stress = Problem(synthetic_city(outages=True))
    genome = tuple(int(i < 5) for i in range(24))
    # Use an affordable set independent of the synthetic fixture's first-site prices.
    genome = tuple(int(i in normal.costs.argsort()[:5]) for i in range(24))
    a, b = normal.evaluate(genome), stress.evaluate(genome)
    assert b.metrics.robust_access <= a.metrics.robust_access
    assert b.metrics.equitable_access <= a.metrics.equitable_access
