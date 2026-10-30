# Synthetic city and custom inputs

`synthetic_city.json` is the canonical fixture: 72 demand clusters, 24 candidate sites, six fictional neighbourhoods and 26 scenarios. It is produced by `synthetic_city(seed=17)` using NumPy PCG64. Every value is invented for a teaching experiment. Coordinates are local kilometers, not longitude/latitude. Costs are abstract units; heat is a multiplier, not Celsius.

Regenerate with the locked environment:

```bash
uv run coolhaven generate --out data
```

The committed JSON, rather than a future library's random generator, is the source of truth for reproducing results.

## Input shape

```json
{
  "name": "Example city",
  "provenance": "Describe the actual source and transformations here.",
  "demand": [
    {"id": "D1", "group": "West", "x": 0.5, "y": 1.0,
     "population": 200, "vulnerability": 0.6, "heat": 1.2}
  ],
  "sites": [
    {"id": "H1", "name": "Community centre", "x": 0.8, "y": 1.1, "cost": 30}
  ],
  "scenarios": [
    {"id": "normal", "walking_multiplier": 1.0, "unavailable": []},
    {"id": "closure", "walking_multiplier": 1.25, "unavailable": ["H1"]}
  ]
}
```

IDs must be unique within a collection. Demand, sites and scenarios must be nonempty. Coordinates must be finite; populations and heat multipliers positive; vulnerabilities within `[0,1]`; costs and walking multipliers positive and finite. Every unavailable site must exist. A chosen hub count and budget must admit at least one feasible set.

Custom scenarios are evaluated exactly as supplied. The application does not automatically invent additional closure scenarios for an uploaded city. The closure toggle removes scenarios whose `unavailable` list is nonempty; it preserves supplied walking scenarios.

The dashboard limits uploads to 60 sites, 500 demand clusters and 80 scenarios to bound interactive work. The CLI has no such UI limit. A large custom dataset may require a smaller population or more memory.
