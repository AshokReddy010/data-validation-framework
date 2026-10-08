"""The checks are trusted only if they find every planted error and nothing else."""
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from generate_data import DAYS, PER_DAY, PLANTED  # noqa: E402

REASON = {
    "missing_records": "missing_record",
    "missing_day": "missing_record",
    "duplicate_records": "duplicate_record",
    "amount_mismatch": "amount_mismatch",
    "wrong_date": "wrong_date",
    "null_amount": "null_amount",
}


@pytest.fixture(scope="session")
def results():
    subprocess.run([sys.executable, "scripts/generate_data.py"], cwd=ROOT, check=True)
    subprocess.run(["dbt", "build", "--profiles-dir", "."], cwd=ROOT, check=True)
    connection = duckdb.connect(str(ROOT / "validation.duckdb"), read_only=True)
    checks = connection.sql("select * from check_results").df()
    exceptions = connection.sql("select * from recon_exceptions").df()
    connection.close()
    return checks, exceptions


def expected_breaks():
    breaks = set()
    for day, source, kind, _ in PLANTED:
        breaks.add((day, source))
        if kind == "wrong_date":
            breaks.add((day + timedelta(days=1), source))
    return breaks


def test_every_source_day_is_checked(results):
    checks, _ = results
    assert len(checks) == DAYS * 2


def test_breaks_are_exactly_the_planted_days(results):
    checks, _ = results
    found = {(row.check_date.date(), row.source)
             for row in checks[checks["status"] == "break"].itertuples()}
    assert found == expected_breaks()


@pytest.mark.parametrize("day,source,kind,records", PLANTED)
def test_reason_and_record_count(results, day, source, kind, records):
    _, exceptions = results
    rows = exceptions[(exceptions["source"] == source)
                      & (exceptions["check_date"].dt.date == day)
                      & (exceptions["reason"] == REASON[kind])]
    assert len(rows) == records


def test_clean_days_have_no_exceptions(results):
    checks, exceptions = results
    clean = {(row.check_date, row.source) for row in checks[checks["status"] == "match"].itertuples()}
    flagged = {(row.check_date, row.source) for row in exceptions.itertuples()}
    assert not clean & flagged


def test_missing_day_counts_every_record(results):
    checks, _ = results
    row = checks[(checks["source"] == "billing") & (checks["actual_count"] == 0)]
    assert len(row) == 1
    assert int(row.iloc[0]["count_diff"]) == -PER_DAY
