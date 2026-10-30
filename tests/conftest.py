import pytest

from coolhaven.model import City, Demand, Problem, Scenario, Site


@pytest.fixture
def tiny_city():
    return City(
        "Two ends",
        "Synthetic unit-test fixture",
        (Demand("D1", "West", 0, 0, 100, 0, 1), Demand("D2", "East", 4, 0, 100, 0, 1)),
        (
            Site("A", "West", 0, 0, 1),
            Site("B", "Midwest", 1, 0, 1),
            Site("C", "East", 4, 0, 1),
            Site("D", "Mideast", 3, 0, 1),
        ),
        (Scenario("normal", 1),),
    )


@pytest.fixture
def tiny(tiny_city):
    return Problem(tiny_city, hubs=2, budget=3, radius=2)
