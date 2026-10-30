# Model and algorithm

## Decision variables and hard constraints

There are `n` candidate sites. A chromosome `x ∈ {0,1}ⁿ` opens site `j` when `x_j = 1`.

```text
sum_j x_j = k
sum_j cost_j × x_j <= B
```

`k` is the hub count, `B` the planning budget, and all costs are positive abstract units. Before searching, the model checks that the cheapest `k` sites fit the budget. Infeasible instances fail explicitly.

## Accessibility

Demand point `i` has population `p_i`, vulnerability `v_i ∈ [0,1]` and a positive synthetic heat multiplier `h_i`. Its weight is:

```text
w_i = p_i × (1 + v_i) × h_i
```

Coordinates are local schematic kilometers. Let `d_ij` be Euclidean distance to site `j`, `r` the walking range, and `m_s` the walking multiplier of scenario `s`:

```text
a_ijs = max(0, 1 − m_s × d_ij / r) if site j is available in scenario s
        0                         otherwise
A_is(x) = max_j (x_j × a_ijs)
```

Each demand point uses the most accessible available selected hub. A score of `0.5` means half the maximum distance-decay accessibility under this model. It does **not** mean that half the residents are safe, served by finite seats or clinically protected. `covered_population` separately counts residents at demand points with positive nominal access.

## Three objectives

For each scenario, take the heat-weighted citywide mean `R_s`. For each neighbourhood `g`, also take a within-group weighted mean `E_gs`:

```text
R_s(x)  = sum_i w_i × A_is(x) / sum_i w_i
E_gs(x) = sum_{i in g} w_i × A_is(x) / sum_{i in g} w_i

R(x) = min_s R_s(x)
E(x) = min_{g,s} E_gs(x)
C(x) = sum_j cost_j × x_j

Minimize: (1 − R(x), 1 − E(x), C(x) / B)
```

`E` is a max-min service objective. It raises the floor for the least-served neighbourhood; it does not directly minimize inequality or enforce equal outcomes. The scenario attaining a group's minimum can differ across groups.

There are 26 default scenarios: normal walking, heatwave walking (`m=1.25`), and 24 heatwave scenarios that each close one candidate site. If that site was not selected, the closure changes nothing. This is deterministic worst-case planning over an explicit finite stress set, with no assumed probabilities. It covers any one selected site's closure during the modeled heatwave, but not simultaneous multi-site failure.

## Evolution

1. Sample `k` sites without replacement and repair budget violations.
2. Compute Pareto ranks and crowding distances.
3. Select each parent using a binary tournament: lower rank, then higher crowding, then a random tie-break.
4. With probability `0.9`, use uniform crossover with an independent `0.5` mask per bit.
5. Repair cardinality and budget. With probability `0.35` **per child**, swap one selected and one unselected site, then repair again.
6. Form the next population from parents and children by elitist rank and crowding truncation. Prefer distinct genomes when enough are available.
7. Keep an external archive of every evaluated non-dominated discovery, including children discarded during population truncation.
8. Stop after the configured number of generations. Generation 0 records the initialized population.

The external archive and preference for unique genomes are practical extensions to the basic NSGA-II flow. The archive preserves discoveries across truncation and makes its fixed-reference hypervolume nondecreasing.

### Constraint repair

Randomly switch excess bits off or missing bits on to reach exactly `k` hubs. While over budget, replace the most expensive selected site with the cheapest unselected site. Every such swap strictly reduces cost. Because the cheapest `k`-set is affordable, repair terminates with a feasible chromosome.

Repair biases proposals toward cheaper sites. Both random search and NSGA-II use this repair, so random search is **not uniform sampling over all feasible sets**. It is a matched proposal baseline.

## Choosing a plan

Evolution does not scalarize the objectives. After search, decision preferences choose a discovered plan by a weighted sum on the fixed normalized scales. Balanced weights are `(0.45, 0.40, 0.15)`; alternative presets are defined in `app.py`. These are illustrative preferences, not fitted or stakeholder-approved values. No hidden normalization to the observed frontier is applied.

## Evaluation protocol

NSGA-II uses `population × (generations + 1)` candidate scoring calls. Random search receives the identical number. Caching skips repeated numerical calculations, but duplicates still consume the candidate budget. Both call counts and unique chromosome counts are reported. Equal calls do not mean equal wall time: sorting, archiving and hypervolume add overhead to NSGA-II.

Greedy forward selection uses the balanced score on partial sets and a cheapest-completion lookahead to preserve feasibility. Nominal access breaks score ties, especially for the first hub, whose single-outage robust access is zero. Its partial-set scoring calls are counted and it uses fewer calls than either search. It is a cheap heuristic reference, not an equal-budget competitor.

Hypervolume is computed exactly as a union of 3D minimization boxes, reference `(1,1,1)`, on `(1−R,1−E,C/B)`. Higher is better. The fixed boundary reference means a plan at the full budget has zero cost-axis extent; comparisons are meaningful only under identical model settings. Hypervolumes from different budgets or scenarios should not be compared directly.

The tests use independent inclusion-exclusion volume calculations, hand-computed accessibility examples, an iterative non-dominance oracle and exact enumeration on small instances. Exact enumeration is capped at 100,000 candidate combinations. The full 24-choose-5 case has 42,504 combinations, but routine tests intentionally use tiny fixtures.

## Limitations

- One synthetic city and five optimizer seeds measure search variability, not geographic generalization. There is no significance test or universal performance claim.
- Coordinates, costs, heat and vulnerability values are synthetic. No census, medical or measured weather data are used.
- Straight-line distance ignores roads, rivers, shade, crossings and mobility constraints.
- Hubs have unlimited capacity, identical service quality and no opening hours.
- Group weights describe fictional neighbourhoods, not protected demographic groups.
- Outages are a finite stress set, not probabilistic forecasts or guarantees against all failures.
- Repair introduces a proposal bias. Search has no global optimality guarantee on the default instance.
- The distance-decay function is chosen for transparency and is not empirically calibrated.
