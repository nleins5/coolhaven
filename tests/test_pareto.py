from itertools import combinations

import numpy as np
import pytest

from coolhaven.pareto import compromise, crowding, dominates, hypervolume, sort_fronts


def test_known_front_partition_and_equal_objectives():
    values = np.array([[0, 1, 0], [1, 0, 0], [1, 1, 1], [2, 2, 2], [0, 1, 0]])
    assert sort_fronts(values) == [[0, 1, 4], [2], [3]]
    assert not dominates(values[0], values[4])


def test_front_sort_matches_independent_iterative_oracle():
    rng = np.random.default_rng(9)
    values = rng.integers(0, 9, (40, 3))
    remaining = list(range(len(values)))
    expected = []
    while remaining:
        front = [
            i
            for i in remaining
            if not any(
                all(values[j, k] <= values[i, k] for k in range(3))
                and any(values[j, k] < values[i, k] for k in range(3))
                for j in remaining
            )
        ]
        expected.append(front)
        remaining = [i for i in remaining if i not in front]
    assert sort_fronts(values) == expected


def test_crowding_preserves_extremes_and_skips_flat_dimensions():
    distances = crowding(np.array([[0, 4], [0.2, 4], [0.7, 4], [1, 4]]))
    assert np.isinf(distances[0]) and np.isinf(distances[-1])
    assert distances[1] == pytest.approx(0.7)
    assert distances[2] == pytest.approx(0.8)
    assert np.isfinite(crowding(np.ones((5, 3)))).all()


def test_hypervolume_uses_union_not_sum_of_overlapping_boxes():
    assert hypervolume([[0.2, 0.3, 0.4]]) == pytest.approx(0.8 * 0.7 * 0.6)
    assert hypervolume([[0, 0, 0], [0.5, 0.5, 0.5]]) == pytest.approx(1)
    assert hypervolume([]) == 0
    assert hypervolume([[1, 0, 0], [2, 2, 2]]) == 0


@pytest.mark.parametrize("seed", range(6))
def test_hypervolume_matches_inclusion_exclusion_oracle(seed):
    points = np.random.default_rng(seed).uniform(0, 1, (6, 3))
    expected = 0
    for size in range(1, len(points) + 1):
        for subset in combinations(points, size):
            intersection = np.prod(1 - np.max(subset, axis=0))
            expected += (-1) ** (size + 1) * intersection
    assert hypervolume(points) == pytest.approx(expected, abs=1e-12)


def test_invalid_decision_weights_are_rejected(tiny):
    candidate = tiny.evaluate((1, 0, 1, 0))
    with pytest.raises(ValueError):
        compromise([candidate], (0, 0, 0))
