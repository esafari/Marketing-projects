# Three end-to-end projects

X Canada is a weekly meal-kit subscription (HelloFresh-class). Each project has its own grain, warehouse, and cloud. Full problem, assumptions, math, and how to test are in that project's `README.md`.

| Project | Grain | Production | Full write-up |
|---|---|---|---|
| `01_mmm_channel_optimization` | National week, each advertising channel | Azure | [README](01_mmm_channel_optimization/README.md) |
| `02_customer_lifetime_value` | Household snapshot Saturday | Azure (Sunday job) | [README](02_customer_lifetime_value/README.md) |
| `03_causal_effects` | Geo × week, household, or session | Amazon Web Services | [README](03_causal_effects/README.md) |

Each folder has `problem/`, `data_engineering/`, `development/`, and `production/`.

Start the studio from the repo root: `python run_webapp.py` → http://127.0.0.1:5050/
