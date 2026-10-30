"""Scenario validation and deterministic accessibility evaluation.

Access is a dimensionless distance-decay proxy, not a clinical protection estimate.
All objectives are minimized; budget and hub count are hard constraints.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

Genome = tuple[int, ...]


@dataclass(frozen=True)
class Demand:
    id: str
    group: str
    x: float
    y: float
    population: int
    vulnerability: float
    heat: float


@dataclass(frozen=True)
class Site:
    id: str
    name: str
    x: float
    y: float
    cost: float


@dataclass(frozen=True)
class Scenario:
    id: str
    walking_multiplier: float
    unavailable: tuple[str, ...] = ()


@dataclass(frozen=True)
class City:
    name: str
    provenance: str
    demand: tuple[Demand, ...]
    sites: tuple[Site, ...]
    scenarios: tuple[Scenario, ...]

    def validate(self) -> None:
        if not self.demand or not self.sites or not self.scenarios:
            raise ValueError("Demand, sites and scenarios must be non-empty.")
        for records in (self.demand, self.sites, self.scenarios):
            ids = [r.id for r in records]
            if any(not isinstance(i, str) or not i for i in ids) or len(ids) != len(set(ids)):
                raise ValueError("IDs must be non-empty and unique within each collection.")
        for d in self.demand:
            values = (d.x, d.y, d.population, d.vulnerability, d.heat)
            if not all(math.isfinite(v) for v in values):
                raise ValueError("Demand numbers must be finite.")
            if d.population <= 0 or not 0 <= d.vulnerability <= 1 or d.heat <= 0 or not d.group:
                raise ValueError("Invalid demand population, vulnerability, heat or group.")
        for s in self.sites:
            if not all(math.isfinite(v) for v in (s.x, s.y, s.cost)) or s.cost <= 0:
                raise ValueError("Site coordinates must be finite and costs positive.")
        site_ids = {s.id for s in self.sites}
        for scenario in self.scenarios:
            if not math.isfinite(scenario.walking_multiplier) or scenario.walking_multiplier <= 0:
                raise ValueError("Walking multipliers must be finite and positive.")
            if not set(scenario.unavailable) <= site_ids:
                raise ValueError("Scenario references an unknown site.")

    def to_dict(self) -> dict:
        return asdict(self)


def load_city(path: str | Path) -> City:
    data = json.loads(Path(path).read_text())
    city = City(
        name=data["name"],
        provenance=data["provenance"],
        demand=tuple(Demand(**d) for d in data["demand"]),
        sites=tuple(Site(**s) for s in data["sites"]),
        scenarios=tuple(
            Scenario(s["id"], s["walking_multiplier"], tuple(s.get("unavailable", [])))
            for s in data["scenarios"]
        ),
    )
    city.validate()
    return city


@dataclass(frozen=True)
class Metrics:
    robust_access: float
    equitable_access: float
    cost: float
    nominal_access: float
    covered_population: int
    scenario_access: tuple[float, ...]
    group_access: tuple[float, ...]


@dataclass(frozen=True)
class Candidate:
    genome: Genome
    objectives: tuple[float, float, float]
    metrics: Metrics


class Problem:
    def __init__(self, city: City, hubs: int = 5, budget: float = 210, radius: float = 2.4):
        city.validate()
        if isinstance(hubs, bool) or not isinstance(hubs, int) or not 1 <= hubs <= len(city.sites):
            raise ValueError("Hub count must be an integer between 1 and the number of sites.")
        if not math.isfinite(budget) or not math.isfinite(radius) or budget <= 0 or radius <= 0:
            raise ValueError("Budget and radius must be finite and positive.")
        self.city, self.hubs, self.budget, self.radius = city, hubs, budget, radius
        self.costs = np.array([s.cost for s in city.sites])
        if np.sort(self.costs)[:hubs].sum() > budget + 1e-9:
            raise ValueError("Budget cannot fund even the cheapest feasible set of hubs.")
        self.population = np.array([d.population for d in city.demand])
        weights = np.array(
            [d.population * (1 + d.vulnerability) * d.heat for d in city.demand], dtype=float
        )
        self.weights = weights / weights.sum()
        self.groups = tuple(sorted({d.group for d in city.demand}))
        self.group_weights = np.array(
            [
                [w if d.group == g else 0 for d, w in zip(city.demand, weights, strict=True)]
                for g in self.groups
            ]
        )
        self.group_weights /= self.group_weights.sum(axis=1, keepdims=True)
        points = np.array([(d.x, d.y) for d in city.demand])
        sites = np.array([(s.x, s.y) for s in city.sites])
        distances = np.linalg.norm(points[:, None, :] - sites[None, :, :], axis=2)
        self.nominal_access = np.clip(1 - distances / radius, 0, 1)
        scenario_arrays = []
        for scenario in city.scenarios:
            access = np.clip(1 - distances * scenario.walking_multiplier / radius, 0, 1)
            access[:, [i for i, s in enumerate(city.sites) if s.id in scenario.unavailable]] = 0
            scenario_arrays.append(access)
        self.access = np.array(scenario_arrays)
        self.cache: dict[Genome, Candidate] = {}
        self.calls = 0

    def feasible(self, genome: Genome) -> bool:
        return (
            len(genome) == len(self.costs)
            and all(bit in (0, 1) for bit in genome)
            and sum(genome) == self.hubs
            and float(self.costs @ genome) <= self.budget + 1e-9
        )

    def metrics(self, genome: Genome) -> Metrics:
        """Allow partial sets for greedy construction; evaluate() enforces feasibility."""
        selected = np.flatnonzero(genome)
        if len(selected):
            access = self.access[:, :, selected].max(axis=2)
            nominal = self.nominal_access[:, selected].max(axis=1)
        else:
            access = np.zeros(self.access.shape[:2])
            nominal = np.zeros(len(self.city.demand))
        scenario_access = access @ self.weights
        group_access = (access @ self.group_weights.T).min(axis=0)
        return Metrics(
            robust_access=float(scenario_access.min()),
            equitable_access=float(group_access.min()),
            cost=float(self.costs @ genome),
            nominal_access=float(nominal @ self.weights),
            covered_population=int(self.population[nominal > 0].sum()),
            scenario_access=tuple(map(float, scenario_access)),
            group_access=tuple(map(float, group_access)),
        )

    def evaluate(self, genome: Genome) -> Candidate:
        if not self.feasible(genome):
            raise ValueError("Genome violates binary encoding, hub count or budget.")
        self.calls += 1
        if genome not in self.cache:
            m = self.metrics(genome)
            self.cache[genome] = Candidate(
                genome, (1 - m.robust_access, 1 - m.equitable_access, m.cost / self.budget), m
            )
        return self.cache[genome]
