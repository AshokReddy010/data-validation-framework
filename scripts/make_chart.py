"""Draw the daily amount difference for each source against the reference."""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
COLOURS = {"client_feed": "#1D5BFF", "billing": "#C96A00"}
LABELS = {"client_feed": "Client file feed", "billing": "Billing database"}


def main():
    results = pd.read_csv(ROOT / "reports" / "check_results.csv", parse_dates=["check_date"])
    figure, axes = plt.subplots(2, 1, figsize=(9, 5.2), sharex=True)
    for axis, source in zip(axes, ["client_feed", "billing"], strict=True):
        part = results[results["source"] == source]
        axis.axhline(0, color="#8A8F98", linewidth=0.8)
        axis.bar(part["check_date"], part["amount_diff"] / 1000, width=0.8, color=COLOURS[source])
        for row in part[part["status"] == "break"].itertuples():
            offset = 6 if row.amount_diff >= 0 else -12
            axis.annotate(row.reasons.split(":")[0].replace("_", " "),
                          (row.check_date, row.amount_diff / 1000),
                          textcoords="offset points", xytext=(0, offset),
                          ha="center", fontsize=8, color="#30343B")
        axis.set_title(f"{LABELS[source]} against the transaction system", loc="left",
                       fontsize=10, fontweight="bold")
        axis.set_ylabel("Difference (thousands)", fontsize=8)
        axis.spines[["top", "right"]].set_visible(False)
        axis.tick_params(labelsize=8)
        axis.margins(y=0.25)
    axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    figure.suptitle("Daily total difference by source: a day with no bar reconciled",
                    x=0.01, ha="left", fontsize=11)
    figure.tight_layout()
    out = ROOT / "reports" / "figures"
    out.mkdir(parents=True, exist_ok=True)
    figure.savefig(out / "daily_differences.png", dpi=150)
    print(f"chart saved to {out / 'daily_differences.png'}")


if __name__ == "__main__":
    main()
