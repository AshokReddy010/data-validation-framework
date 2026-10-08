# Data Validation Framework

[![CI](https://github.com/AshokReddy010/data-validation-framework/actions/workflows/ci.yml/badge.svg)](https://github.com/AshokReddy010/data-validation-framework/actions/workflows/ci.yml)

Three systems hold the same transactions: the transaction system, a client file feed and the billing database. Before any report goes out, they should agree. This project checks that they do, every day, and says exactly which records are wrong when they do not.

It is a public example of the kind of reconciliation checks I build at work. All data here is invented, and no employer code, data or business rule is used.

## What it found

The data generator plants six errors in 60 days of invented transactions. The checks found all six, gave the right reason for each, and raised nothing on the 113 clean source-days.

![Daily difference by source](reports/figures/daily_differences.png)

| Day | Source | Count difference | Amount difference | Reason found |
|:--|:--|--:|--:|:--|
| 14 Jul | Client feed | -37 | -114,056.53 | 37 records missing |
| 22 Jul | Billing | +25 | +63,481.27 | 25 records billed twice |
| 3 Aug | Client feed | 0 | +1,200.00 | 12 amounts differ |
| 11 Aug | Billing | -200 | -502,825.44 | The whole day is missing |
| 19 Aug | Billing | -9 | -19,555.54 | 9 records filed under the next day |
| 20 Aug | Billing | +9 | +19,555.54 | The same 9 records, landing a day late |
| 25 Aug | Client feed | 0 | -12,219.57 | 5 amounts are blank |

Two of these would pass a row count: on 3 August and 25 August every record is present, and only the totals show a problem.

## How it works

The checks run in two levels, so most days cost one cheap comparison.

| Level | Model | What it does |
|:--|:--|:--|
| 1 | `daily_totals` | Counts the rows and sums the amounts per source per day |
| 1 | `recon_daily` | Compares each source with the transaction system and marks each day `match` or `break` |
| 2 | `recon_exceptions` | For records that disagree, names the reason: missing, duplicate, wrong date, blank amount or different amount |
| Output | `check_results` | One row per source per day with the status, the differences and the reasons, for a dashboard or an alert to read |

```
scripts/generate_data.py     three invented sources, six planted errors
        │
dbt (DuckDB)
  ├─ staging                 cast types, treat blank amounts as null
  ├─ daily_totals            level 1: counts and totals
  ├─ recon_daily             level 1: match or break, per source per day
  ├─ recon_exceptions        level 2: the records behind each break
  └─ check_results           the table people read
        │
scripts/run_checks.py        report, chart and alert
```

## Tests

- **21 dbt data tests.** Keys are unique and present, every feed and billing record points to a real transaction, and three tests guard the checks themselves:
  - every break has a record-level reason,
  - no clean day hides exception records, which would mean two errors cancelled out in the totals,
  - a warning is raised while any break is open.
- **10 pytest checks** that the breaks found are exactly the planted ones, with the right reason and record count for each.

The second of those tests caught a real gap while I was building this. A record filed under the wrong day throws off two days, the one it left and the one it landed on. My first drill-down explained only the first, and the test failed until it explained both.

## Scheduling and alerts

- `scheduled-validation.yml` runs the checks every day on GitHub Actions and can be started by hand.
- The report is written to the run summary and saved as a file with the run.
- If an `ALERT_WEBHOOK_URL` secret is set, a break posts a message to that chat webhook.

## Run it yourself

Needs Python 3.10 or newer. Commands are for Windows CMD.

```
git clone https://github.com/AshokReddy010/data-validation-framework.git
cd data-validation-framework
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

python scripts\run_checks.py
pytest -q unit_tests
```

`run_checks.py` creates the data, builds the checks and writes `reports/summary.md`, `reports/check_results.csv`, `reports/exceptions.csv` and the chart. Add `--fail-on-break` to make it exit with an error while any break is open.

## Limitations

- The data is invented and small: 12,000 transactions over 60 days. It shows the method, not performance at scale.
- The transaction system is treated as correct. A record wrong in that system and repeated faithfully by the others would not be caught.
- Matching is by transaction ID. Sources without a shared key would need a matching step first.
- It runs on DuckDB. The models use standard SQL and dbt, so moving them to a cloud warehouse is a change of profile, which is the planned next step.
- A scheduler such as Airflow would replace the GitHub Actions schedule in a production set-up.

## Tools

Python, SQL, dbt, DuckDB, pandas, Matplotlib, pytest, GitHub Actions.

## Author

Ashok Reddy Bhimavarapu · [Portfolio](https://ashokreddy010.github.io) · [LinkedIn](https://www.linkedin.com/in/ashokreddy1)
