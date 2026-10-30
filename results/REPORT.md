# Benchmark results

Synthetic city; five hubs, explicit stress scenarios. Scores measure model accessibility, not real-world health outcomes.

| Method | Hypervolume mean ± sample SD | Robust access mean | Worst-group mean |
|---|---:|---:|---:|
| NSGA-II | 0.031266 ± 0.000172 | 53.027% | 15.318% |
| Random search | 0.026854 ± 0.000743 | 52.512% | 17.864% |
| Greedy | 0.005491 ± 0.000000 | 42.014% | 3.564% |

NSGA-II and random search each use **3,904 candidate scoring calls per seed**, including duplicates. Unique counts are reported in the CSV.

Hypervolume compares complete returned frontiers. Access columns describe one post-hoc compromise with fixed preference weights (0.45, 0.40, 0.15). They need not improve together. Greedy is deterministic and uses fewer calls. These runs do not establish statistical significance or general superiority.
