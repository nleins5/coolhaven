"""Non-dominated sorting, crowding and exact three-dimensional hypervolume."""

from __future__ import annotations

import numpy as np

from coolhaven.model import Candidate


def dominates(a, b) -> bool:
    return all(x <= y for x, y in zip(a, b, strict=True)) and any(
        x < y for x, y in zip(a, b, strict=True)
    )


def sort_fronts(values: np.ndarray) -> list[list[int]]:
    values = np.asarray(values, dtype=float)
    if len(values) == 0:
        return []
    relation = (values[:, None, :] <= values[None, :, :]).all(axis=2) & (
        values[:, None, :] < values[None, :, :]
    ).any(axis=2)
    counts = relation.sum(axis=0)
    current = np.flatnonzero(counts == 0).tolist()
    fronts = []
    while current:
        fronts.append(current)
        counts[current] = -1
        counts -= relation[current].sum(axis=0)
        current = np.flatnonzero(counts == 0).tolist()
    return fronts


def crowding(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    distances = np.zeros(len(values))
    if len(values) <= 2:
        distances[:] = np.inf
        return distances
    for axis in range(values.shape[1]):
        order = np.argsort(values[:, axis], kind="stable")
        span = values[order[-1], axis] - values[order[0], axis]
        if span == 0:
            continue
        distances[order[[0, -1]]] = np.inf
        distances[order[1:-1]] += (values[order[2:], axis] - values[order[:-2], axis]) / span
    return distances


def frontier(candidates: list[Candidate]) -> list[Candidate]:
    unique = {c.genome: c for c in candidates}
    items = list(unique.values())
    if not items:
        return []
    indices = sort_fronts(np.array([c.objectives for c in items]))[0]
    return sorted((items[i] for i in indices), key=lambda c: (c.objectives, c.genome))


def hypervolume(values, reference=(1.0, 1.0, 1.0)) -> float:
    """Exact volume of the union of minimization boxes, clipped at a common reference."""
    points = np.asarray(values, dtype=float)
    ref = np.asarray(reference, dtype=float)
    if points.size == 0:
        return 0.0
    if points.ndim != 2 or points.shape[1] != 3 or ref.shape != (3,):
        raise ValueError("Hypervolume requires three objectives and a 3D reference.")
    if not np.isfinite(points).all() or not np.isfinite(ref).all():
        raise ValueError("Hypervolume inputs must be finite.")
    points = points[(points < ref).all(axis=1)]
    if not len(points):
        return 0.0
    points = points[sort_fronts(points)[0]]
    xs = sorted(set(points[:, 0]) | {ref[0]})
    volume = 0.0
    for left, right in zip(xs[:-1], xs[1:], strict=True):
        active = points[points[:, 0] <= left, 1:]
        ys = sorted(set(active[:, 0]) | {ref[1]})
        area = 0.0
        for low, high in zip(ys[:-1], ys[1:], strict=True):
            z = active[active[:, 0] <= low, 1].min()
            area += (high - low) * (ref[2] - z)
        volume += (right - left) * area
    return float(volume)


def compromise(candidates: list[Candidate], weights=(0.45, 0.4, 0.15)) -> Candidate:
    """Preference-weighted choice on fixed [0,1] objective scales, after evolution."""
    if len(weights) != 3 or any(w < 0 for w in weights) or sum(weights) <= 0:
        raise ValueError("Three nonnegative preference weights with a positive sum are required.")
    if not candidates:
        raise ValueError("Cannot select from an empty frontier.")
    return min(
        candidates,
        key=lambda c: (
            sum(w * v for w, v in zip(weights, c.objectives, strict=True)),
            c.objectives,
            c.genome,
        ),
    )
