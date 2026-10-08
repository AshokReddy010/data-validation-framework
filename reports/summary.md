# Validation report

- Days checked: 60
- Source-day comparisons: 120
- Matching: 113
- Breaks: 7
- Records behind the breaks: 297

## Days that did not reconcile

| Day | Source | Count difference | Amount difference | Reason found |
|:--|:--|--:|--:|:--|
| 2026-07-14 | client_feed | -37 | -114,056.53 | missing_record: 37 |
| 2026-07-22 | billing | +25 | +63,481.27 | duplicate_record: 25 |
| 2026-08-03 | client_feed | +0 | +1,200.00 | amount_mismatch: 12 |
| 2026-08-11 | billing | -200 | -502,825.44 | missing_record: 200 |
| 2026-08-19 | billing | -9 | -19,555.54 | wrong_date: 9 |
| 2026-08-20 | billing | +9 | +19,555.54 | wrong_date: 9 |
| 2026-08-25 | client_feed | +0 | -12,219.57 | null_amount: 5 |
