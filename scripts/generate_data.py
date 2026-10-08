"""Create three invented source extracts with known errors planted in them.

Everything here is synthetic. The three sources imitate a common set-up:
a transaction system (treated as the reference), a client file feed and a
billing database that should all agree before data is delivered.
"""
import argparse
import csv
import random
from datetime import date, timedelta
from pathlib import Path

START = date(2026, 7, 1)
DAYS = 60
PER_DAY = 200

# Each planted error: (day, source, kind, how many records it touches)
PLANTED = [
    (date(2026, 7, 14), "client_feed", "missing_records", 37),
    (date(2026, 7, 22), "billing", "duplicate_records", 25),
    (date(2026, 8, 3), "client_feed", "amount_mismatch", 12),
    (date(2026, 8, 11), "billing", "missing_day", PER_DAY),
    (date(2026, 8, 19), "billing", "wrong_date", 9),
    (date(2026, 8, 25), "client_feed", "null_amount", 5),
]


def build(seed=7):
    rng = random.Random(seed)
    transactions, feed, billing = [], [], []
    txn_no = 0
    bill_no = 0
    for offset in range(DAYS):
        day = START + timedelta(days=offset)
        todays = []
        for _ in range(PER_DAY):
            txn_no += 1
            todays.append({
                "txn_id": f"T{txn_no:06d}",
                "account_id": f"A{rng.randint(1, 400):04d}",
                "txn_date": day.isoformat(),
                "amount": round(rng.uniform(25, 5000), 2),
                "status": "settled",
            })
        transactions.extend(todays)
        plants = {(src, kind): n for d, src, kind, n in PLANTED if d == day}

        feed_rows = [{"record_id": t["txn_id"], "account": t["account_id"],
                      "trade_date": t["txn_date"], "amount": t["amount"]} for t in todays]
        if ("client_feed", "missing_records") in plants:
            feed_rows = feed_rows[:-plants[("client_feed", "missing_records")]]
        if ("client_feed", "amount_mismatch") in plants:
            for row in feed_rows[:plants[("client_feed", "amount_mismatch")]]:
                row["amount"] = round(row["amount"] + 100.0, 2)
        if ("client_feed", "null_amount") in plants:
            for row in feed_rows[:plants[("client_feed", "null_amount")]]:
                row["amount"] = ""
        feed.extend(feed_rows)

        if ("billing", "missing_day") in plants:
            continue
        bill_rows = []
        for t in todays:
            bill_no += 1
            bill_rows.append({"billing_id": f"B{bill_no:06d}", "txn_id": t["txn_id"],
                              "bill_date": t["txn_date"], "billed_amount": t["amount"]})
        if ("billing", "duplicate_records") in plants:
            for row in bill_rows[:plants[("billing", "duplicate_records")]]:
                bill_no += 1
                bill_rows.append({**row, "billing_id": f"B{bill_no:06d}"})
        if ("billing", "wrong_date") in plants:
            next_day = (day + timedelta(days=1)).isoformat()
            for row in bill_rows[:plants[("billing", "wrong_date")]]:
                row["bill_date"] = next_day
        billing.extend(bill_rows)
    return transactions, feed, billing


def write(rows, path):
    with open(path, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="data/raw")
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    transactions, feed, billing = build()
    write(transactions, out / "transactions.csv")
    write(feed, out / "client_feed.csv")
    write(billing, out / "billing.csv")
    write([{"check_date": d.isoformat(), "source": s, "kind": k, "records": n}
           for d, s, k, n in PLANTED], out / "planted_errors.csv")
    print(f"transactions {len(transactions):,} | client_feed {len(feed):,} | billing {len(billing):,}")
    print(f"planted errors: {len(PLANTED)} (listed in {out / 'planted_errors.csv'})")


if __name__ == "__main__":
    main()
