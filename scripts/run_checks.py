"""Run the whole validation: create the data, build the checks, write the
report and raise an alert when a day does not reconcile.

Usage:
    python scripts/run_checks.py                 report breaks, exit 0
    python scripts/run_checks.py --fail-on-break exit 1 when any break is open
"""
import argparse
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"


def run(command):
    print("$", " ".join(command))
    subprocess.run(command, cwd=ROOT, check=True)


def write_reports():
    connection = duckdb.connect(str(ROOT / "validation.duckdb"), read_only=True)
    results = connection.sql("select * from check_results order by check_date, source").df()
    exceptions = connection.sql("select * from recon_exceptions order by check_date, source, txn_id").df()
    connection.close()

    REPORTS.mkdir(exist_ok=True)
    results.to_csv(REPORTS / "check_results.csv", index=False)
    exceptions.to_csv(REPORTS / "exceptions.csv", index=False)

    breaks = results[results["status"] == "break"]
    days = results["check_date"].nunique()
    lines = [
        "# Validation report",
        "",
        f"- Days checked: {days}",
        f"- Source-day comparisons: {len(results)}",
        f"- Matching: {len(results) - len(breaks)}",
        f"- Breaks: {len(breaks)}",
        f"- Records behind the breaks: {len(exceptions)}",
        "",
    ]
    if breaks.empty:
        lines.append("Every source agreed with the reference on every day.")
    else:
        lines += [
            "## Days that did not reconcile",
            "",
            "| Day | Source | Count difference | Amount difference | Reason found |",
            "|:--|:--|--:|--:|:--|",
        ]
        for row in breaks.itertuples():
            lines.append(f"| {row.check_date:%Y-%m-%d} | {row.source} | {row.count_diff:+d} | "
                         f"{row.amount_diff:+,.2f} | {row.reasons} |")
    report = "\n".join(lines) + "\n"
    (REPORTS / "summary.md").write_text(report)
    return report, breaks


def alert(report, breaks):
    """Send the report where people will see it."""
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_file:
        with open(summary_file, "a") as handle:
            handle.write(report)
    webhook = os.environ.get("ALERT_WEBHOOK_URL")
    if webhook and not breaks.empty:
        text = f"Data validation: {len(breaks)} source-day breaks. See reports/summary.md."
        request = urllib.request.Request(
            webhook, data=json.dumps({"text": text}).encode(),
            headers={"Content-Type": "application/json"})
        urllib.request.urlopen(request, timeout=20)
        print("alert sent to the webhook")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fail-on-break", action="store_true")
    args = parser.parse_args()

    run([sys.executable, "scripts/generate_data.py"])
    run(["dbt", "build", "--profiles-dir", "."])
    report, breaks = write_reports()
    run([sys.executable, "scripts/make_chart.py"])
    print()
    print(report)
    alert(report, breaks)
    if args.fail_on_break and not breaks.empty:
        sys.exit(1)


if __name__ == "__main__":
    main()
