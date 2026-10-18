"""Live mode: a rolling 60-day window of simulated feeds with faults injected at random, checked every day.

Every morning the scheduled workflow regenerates the three sources for the 60 days up to yesterday. Each
source-day has a small chance of one fault (missing records, duplicates, changed or blank amounts, a missing
day, records filed a day late). Faults are drawn from a generator seeded by the date, so a day always gets the
same fault however many times it is rebuilt, and new days bring new faults.

The dbt checks never see the list of injected faults. This script compares what they found with what was
injected and publishes site/data/status.json for the live page: per day and source, what was injected, what
the checks reported, and whether they agree.

    python scripts/live.py                 build, check and score the window ending yesterday
    python scripts/live.py --end 2026-10-17
"""

import argparse
import json
import os
import random
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from generate_data import build, write  # noqa: E402

WINDOW = 60
PER_DAY = 200
FAULT_RATE = 0.06
KINDS = {
    "client_feed": ["missing_records", "duplicate_records", "amount_mismatch", "null_amount"],
    "billing": ["missing_records", "duplicate_records", "amount_mismatch", "missing_day", "wrong_date"],
}
REASON = {"missing_records": "missing_record", "missing_day": "missing_record", "duplicate_records": "duplicate_record",
          "amount_mismatch": "amount_mismatch", "wrong_date": "wrong_date", "null_amount": "null_amount"}
SIZE = {"missing_records": (5, 60), "duplicate_records": (3, 30), "amount_mismatch": (2, 20), "null_amount": (1, 10),
        "wrong_date": (3, 15)}


def faults_for(day: date, last_day: date) -> list[tuple[date, str, str, int]]:
    """The faults injected on one day: deterministic for the date, at most one per source."""
    rng = random.Random(f"faults-{day.isoformat()}")
    out = []
    for source, kinds in KINDS.items():
        if rng.random() >= FAULT_RATE:
            continue
        kind = rng.choice([k for k in kinds if not (k == "wrong_date" and day == last_day)])
        n = PER_DAY if kind == "missing_day" else rng.randint(*SIZE[kind])
        out.append((day, source, kind, n))
    return out


def window_faults(end: date) -> list[tuple[date, str, str, int]]:
    start = end - timedelta(days=WINDOW - 1)
    faults = []
    for k in range(WINDOW):
        faults += faults_for(start + timedelta(days=k), end)
    return faults


def generate(end: date, out: Path) -> list[tuple[date, str, str, int]]:
    start = end - timedelta(days=WINDOW - 1)
    faults = window_faults(end)
    # one fault per source-day keeps every injected fault separately scorable; wrong_date also touches the next
    # day, so a second fault there would be ambiguous: drop it
    taken = {(d + timedelta(days=1), s) for d, s, k, _ in faults if k == "wrong_date"}
    faults = [f for f in faults if (f[0], f[1]) not in taken]
    transactions, feed, billing = build(seed=int(start.strftime("%Y%m%d")), start=start, days=WINDOW, planted=faults,
                                        per_day=PER_DAY)
    out.mkdir(parents=True, exist_ok=True)
    write(transactions, out / "transactions.csv")
    write(feed, out / "client_feed.csv")
    write(billing, out / "billing.csv")
    return faults


def score(db: Path, faults: list[tuple[date, str, str, int]], end: date) -> dict:
    con = duckdb.connect(str(db), read_only=True)
    checks = con.sql("select check_date, source, status, count_diff, amount_diff, reasons from check_results").fetchall()
    exc = con.sql("""select check_date, source, reason, count(*) n from recon_exceptions group by 1, 2, 3""").fetchall()
    samples = con.sql("""
        select check_date, source, reason, txn_id, expected_amount, actual_amount
        from (select *, row_number() over (partition by check_date, source order by txn_id) rn from recon_exceptions)
        where rn <= 5 order by check_date, source, txn_id""").fetchall()
    con.close()

    expected: dict[tuple[str, str], dict] = {}
    for d, s, k, n in faults:
        expected[(d.isoformat(), s)] = {"kind": k, "records": n, "reason": REASON[k]}
        if k == "wrong_date":
            expected[((d + timedelta(days=1)).isoformat(), s)] = {"kind": "wrong_date (spill-over)", "records": n,
                                                                    "reason": "wrong_date"}
    found = {}
    for d, s, reason, n in exc:
        found.setdefault((d.isoformat(), s), {})[reason] = n
    sample_map: dict[tuple[str, str], list] = {}
    for d, s, reason, txn, ea, aa in samples:
        sample_map.setdefault((d.isoformat(), s), []).append(
            [txn, reason, None if ea is None else float(ea), None if aa is None else float(aa)])

    days = []
    tp = fn = fp = 0
    for d, s, status, cdiff, adiff, reasons in sorted(checks):
        key = (d.isoformat(), s)
        exp = expected.get(key)
        got = found.get(key, {})
        if exp and status == "break" and exp["reason"] in got and len(got) == 1:
            verdict = "caught"
            tp += 1 if "spill" not in exp["kind"] else 0
        elif exp:
            verdict = "missed" if status == "match" else "wrong_reason"
            fn += 1 if "spill" not in exp["kind"] else 0
        elif status == "break":
            verdict = "false_alarm"
            fp += 1
        else:
            verdict = "clean"
        days.append({"day": key[0], "source": s, "status": status, "count_diff": int(cdiff),
                     "amount_diff": round(float(adiff), 2), "reasons": reasons, "injected": exp, "found": got,
                     "verdict": verdict, "samples": sample_map.get(key, [])})
    return {"generated_at": datetime.now(timezone.utc).isoformat(), "window": [days[0]["day"], end.isoformat()],
            "records_per_day": PER_DAY, "fault_rate": FAULT_RATE,
            "score": {"injected": tp + fn, "caught": tp, "missed_or_wrong": fn, "false_alarms": fp,
                      "source_days": len(days)},
            "days": days}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--end", type=date.fromisoformat, default=datetime.now(timezone.utc).date() - timedelta(days=1))
    p.add_argument("--out", type=Path, default=ROOT / "site" / "data" / "status.json")
    args = p.parse_args(argv)
    raw = ROOT / "data" / "live"
    db = ROOT / "live.duckdb"
    faults = generate(args.end, raw)
    env = {**os.environ, "DV_RAW_DIR": str(raw), "DV_DB": str(db)}
    subprocess.run(["dbt", "build", "--profiles-dir", ".", "--target-path", "target_live"], cwd=ROOT, env=env, check=True)
    status = score(db, faults, args.end)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(status, separators=(",", ":"), default=str), encoding="utf-8")
    s = status["score"]
    runs = args.out.parent / "runs.csv"
    new = not runs.exists()
    with runs.open("a", encoding="utf-8") as fh:
        if new:
            fh.write("run_date,window_end,injected,caught,missed_or_wrong,false_alarms\n")
        fh.write(f"{datetime.now(timezone.utc).date()},{args.end},{s['injected']},{s['caught']},"
                 f"{s['missed_or_wrong']},{s['false_alarms']}\n")
    print(f"window {status['window'][0]}..{status['window'][1]}: injected {s['injected']}, caught {s['caught']}, "
          f"missed or wrong {s['missed_or_wrong']}, false alarms {s['false_alarms']}")
    return 0 if s["missed_or_wrong"] == 0 and s["false_alarms"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
