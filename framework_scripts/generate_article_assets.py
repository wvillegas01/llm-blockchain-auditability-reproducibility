from __future__ import annotations

import csv
import json
import os
from pathlib import Path

import matplotlib.pyplot as plt


AUDIT_ROOT = Path(os.environ.get("AUDIT_ROOT", "audit_workspace"))
FRAMEWORK_ROOT = AUDIT_ROOT / "14_framework_consolidation" / "llm_blockchain_audit"
RESULTS = FRAMEWORK_ROOT / "results"
TABLES = RESULTS / "tables"
FIGURES = RESULTS / "figures"


def ensure_dirs() -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    fieldnames = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_markdown_table(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    cols = list(rows[0].keys())
    with path.open("w", encoding="utf-8") as f:
        f.write("| " + " | ".join(cols) + " |\n")
        f.write("|" + "|".join(["---"] * len(cols)) + "|\n")
        for row in rows:
            f.write("| " + " | ".join(str(row.get(c, "")) for c in cols) + " |\n")


def main() -> None:
    ensure_dirs()
    perf = read_csv(AUDIT_ROOT / "13_performance_privacy_evaluator" / "02_outputs" / "performance_metrics.csv")
    privacy = read_csv(AUDIT_ROOT / "13_performance_privacy_evaluator" / "02_outputs" / "privacy_metrics.csv")
    storage = read_csv(AUDIT_ROOT / "13_performance_privacy_evaluator" / "02_outputs" / "storage_metrics.csv")
    tamper = read_csv(AUDIT_ROOT / "12_tampering_simulator" / "02_outputs" / "tampering_results.csv")
    integrity = read_csv(AUDIT_ROOT / "11_cryptographic_integrity_verifier" / "02_outputs" / "cryptographic_integrity_results.csv")

    write_csv(TABLES / "table_performance_metrics.csv", perf)
    write_markdown_table(TABLES / "table_performance_metrics.md", perf)
    write_csv(TABLES / "table_privacy_metrics.csv", privacy)
    write_markdown_table(TABLES / "table_privacy_metrics.md", privacy)
    write_csv(TABLES / "table_storage_metrics.csv", storage)
    write_markdown_table(TABLES / "table_storage_metrics.md", storage)
    write_csv(TABLES / "table_tampering_results.csv", tamper)
    write_markdown_table(TABLES / "table_tampering_results.md", tamper)
    write_csv(TABLES / "table_integrity_results.csv", integrity)
    write_markdown_table(TABLES / "table_integrity_results.md", integrity)

    stages = [row["stage"] for row in perf]
    throughput = [float(row["throughput_records_per_second"]) for row in perf]
    plt.figure(figsize=(9, 4.8))
    plt.barh(stages, throughput, color="#2f6f8f")
    plt.xlabel("Records per second")
    plt.title("Framework throughput by stage")
    plt.tight_layout()
    plt.savefig(FIGURES / "figure_throughput_by_stage.png", dpi=200)
    plt.close()

    storage_labels = [row["artifact"] for row in storage]
    storage_mb = [float(row["size_mb"]) for row in storage]
    plt.figure(figsize=(9, 4.8))
    plt.barh(storage_labels, storage_mb, color="#7a8f2f")
    plt.xlabel("Size (MB)")
    plt.xscale("log")
    plt.title("Storage footprint by artifact")
    plt.tight_layout()
    plt.savefig(FIGURES / "figure_storage_footprint.png", dpi=200)
    plt.close()

    attack_labels = [row["attack_type"] for row in tamper]
    detected = [1 if row["detected"] == "True" else 0 for row in tamper]
    plt.figure(figsize=(9, 4.8))
    plt.barh(attack_labels, detected, color="#8f4f2f")
    plt.xlabel("Detected")
    plt.xlim(0, 1.1)
    plt.title("Tampering detection by attack type")
    plt.tight_layout()
    plt.savefig(FIGURES / "figure_tampering_detection.png", dpi=200)
    plt.close()

    summary = {
        "tables": sorted(p.name for p in TABLES.glob("*")),
        "figures": sorted(p.name for p in FIGURES.glob("*")),
    }
    with (RESULTS / "article_assets_summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(RESULTS)


if __name__ == "__main__":
    main()
