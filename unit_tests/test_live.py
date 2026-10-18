"""Live mode: random faults over a rolling window must all be caught, with the right reason, and nothing else."""
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import live  # noqa: E402


def test_faults_are_deterministic_per_day():
    d = date(2026, 3, 14)
    assert live.faults_for(d, date(2026, 4, 1)) == live.faults_for(d, date(2026, 4, 1))
    start = date(2025, 1, 1)
    every = [f for k in range(400) for f in live.faults_for(start + timedelta(days=k), date(2030, 1, 1))]
    assert 0.03 < len(every) / 800 < 0.09                      # about FAULT_RATE per source-day
    assert {f[2] for f in every} == set(live.REASON)           # every fault kind gets exercised


def test_no_wrong_date_on_the_last_day():
    end = date(2026, 5, 20)
    assert all(not (d == end and k == "wrong_date") for d, _, k, _ in live.window_faults(end))


@pytest.mark.parametrize("end", ["2026-10-17", "2025-07-04"])
def test_live_window_scores_perfectly(end, tmp_path):
    out = tmp_path / "status.json"
    assert live.main(["--end", end, "--out", str(out)]) == 0
    status = json.loads(out.read_text())
    s = status["score"]
    assert s["injected"] > 0 and s["caught"] == s["injected"] and s["false_alarms"] == 0
    assert s["source_days"] == live.WINDOW * 2
    assert (tmp_path / "runs.csv").read_text().count("\n") == 2
