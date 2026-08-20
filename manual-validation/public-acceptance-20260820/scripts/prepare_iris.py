#!/usr/bin/env python3
"""Convert the official UCI Iris data file into a headered validation CSV."""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "sources" / "raw" / "iris" / "iris.data"
OUTPUT = ROOT / "inputs" / "iris.csv"
HEADER = ["sepal_length_cm", "sepal_width_cm", "petal_length_cm", "petal_width_cm", "species"]


def main() -> int:
    rows = []
    with SOURCE.open("r", encoding="utf-8-sig", newline="") as handle:
        for raw in csv.reader(handle):
            if not raw:
                continue
            if len(raw) != 5:
                raise ValueError(f"expected 5 columns, found {len(raw)}")
            values = [float(value) for value in raw[:4]]
            rows.append([*values, raw[4]])
    counts = Counter(row[4] for row in rows)
    if len(rows) != 150 or counts != {
        "Iris-setosa": 50, "Iris-versicolor": 50, "Iris-virginica": 50,
    }:
        raise ValueError(f"unexpected Iris distribution: rows={len(rows)}, classes={dict(counts)}")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADER)
        writer.writerows(rows)
    print(f"Prepared {len(rows)} rows -> {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
