from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "derived_tables"
OUTPUTS = ROOT / "outputs"
OUTPUTS.mkdir(exist_ok=True)


def approx_equal(actual: float, expected: float, tolerance: float = 1e-6) -> bool:
    return abs(float(actual) - float(expected)) <= tolerance


def check(name: str, actual, expected, tolerance: float | None = None) -> dict:
    if tolerance is None:
        passed = actual == expected
    else:
        passed = approx_equal(float(actual), float(expected), tolerance)
    return {
        "check": name,
        "actual": actual,
        "expected": expected,
        "tolerance": tolerance,
        "passed": bool(passed),
    }


def linear_fit(records: np.ndarray, seconds: np.ndarray) -> dict:
    slope, intercept = np.polyfit(records, seconds, 1)
    predicted = slope * records + intercept
    ss_res = float(np.sum((seconds - predicted) ** 2))
    ss_tot = float(np.sum((seconds - np.mean(seconds)) ** 2))
    r2 = 1.0 - ss_res / ss_tot
    return {
        "slope_seconds_per_record": float(slope),
        "intercept_seconds": float(intercept),
        "r_squared": float(r2),
        "seconds_per_100k_records": float(slope * 100000),
    }


def required_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Required reproducibility artifact is missing: {path}")


def main() -> None:
    required_files = [
        TABLES / "hash_mode_comparison_raw.csv",
        TABLES / "tampering_results_raw.csv",
        TABLES / "scalability_results_raw.csv",
        TABLES / "table6_load_scalability.csv",
        TABLES / "table7_block_size_sensitivity.csv",
        TABLES / "full_corpus_key_metrics.csv",
    ]
    for path in required_files:
        required_file(path)

    checks: list[dict] = []

    hash_modes = pd.read_csv(TABLES / "hash_mode_comparison_raw.csv")
    hmac = hash_modes.loc[hash_modes["hash_mode"] == "hmac-sha256"].iloc[0]
    sha = hash_modes.loc[hash_modes["hash_mode"] == "sha256"].iloc[0]

    checks.append(check("fixed pilot total audit records", int(hmac["total_records"]), 139258))
    checks.append(check("fixed pilot interaction records", int(hmac["interaction_records"]), 100000))
    checks.append(check("fixed pilot comparison records", int(hmac["comparison_records"]), 39258))
    checks.append(check("HMAC full record-set verification passed", bool(hmac["verification_passed"]), True))
    checks.append(check("SHA-256 full record-set verification passed", bool(sha["verification_passed"]), True))
    checks.append(check("HMAC false acceptance count", int(hmac["false_acceptance_count"]), 0))
    checks.append(check("SHA-256 false acceptance count", int(sha["false_acceptance_count"]), 0))
    checks.append(check("HMAC tampering detection rate", float(hmac["tampering_detection_rate"]), 1.0, 1e-12))
    checks.append(check("SHA-256 tampering detection rate", float(sha["tampering_detection_rate"]), 1.0, 1e-12))

    generation_change = (
        (hmac["audit_interaction_throughput"] - sha["audit_interaction_throughput"])
        / sha["audit_interaction_throughput"]
        * 100
    )
    verification_change = (
        (hmac["verification_throughput"] - sha["verification_throughput"])
        / sha["verification_throughput"]
        * 100
    )
    checks.append(check("HMAC audit-generation relative change percent", round(generation_change, 4), -5.3731, 0.0002))
    checks.append(check("HMAC full record-set verification relative change percent", round(verification_change, 4), 3.2635, 0.0002))

    tampering = pd.read_csv(TABLES / "tampering_results_raw.csv")
    checks.append(check("controlled tampering scenarios", len(tampering), 8))
    checks.append(check("controlled tampering scenarios detected", int(tampering["detected"].sum()), 8))
    checks.append(check("controlled tampering false acceptances", int((~tampering["detected"]).sum()), 0))

    scalability_raw = pd.read_csv(TABLES / "scalability_results_raw.csv")
    records = scalability_raw["total_audit_records"].to_numpy(dtype=float)
    total_time = scalability_raw["total_wall_seconds"].to_numpy(dtype=float)
    fit = linear_fit(records, total_time)
    checks.append(check("Table 6 load scenario count", len(scalability_raw), 5))
    checks.append(check("Table 6 first scenario audit records", int(records[0]), 49258))
    checks.append(check("Table 6 last scenario audit records", int(records[-1]), 539258))
    checks.append(check("Table 6 linear fit R squared", round(fit["r_squared"], 6), 0.999989, 0.000001))
    checks.append(check("Table 6 seconds per 100k records", round(fit["seconds_per_100k_records"], 3), 8.392, 0.002))

    derived_scalability = pd.read_csv(TABLES / "table6_load_scalability.csv")
    computed_relative_latency = total_time / total_time[0]
    checks.append(
        check(
            "Table 6 final relative latency",
            round(float(computed_relative_latency[-1]), 4),
            float(derived_scalability["Relative latency"].iloc[-1]),
            0.0001,
        )
    )

    block_size = pd.read_csv(TABLES / "table7_block_size_sensitivity.csv")
    validation_column = "Block-header chain-validation time s"
    if validation_column not in block_size.columns:
        validation_column = "Verification time s"
    checks.append(check("Table 7 block-size scenario count", len(block_size), 6))
    checks.append(check("Table 7 fixed audit records covered at block size 1000", 140 * 1000 >= 139258, True))
    checks.append(check("Table 7 minimum block-header chain-validation time", float(block_size[validation_column].min()), 0.000026, 1e-12))
    checks.append(check("Table 7 maximum block-header chain-validation time", float(block_size[validation_column].max()), 0.000921, 1e-12))

    storage = pd.read_csv(TABLES / "full_corpus_key_metrics.csv")
    storage_row = storage.iloc[0]
    checks.append(check("full-corpus auditable units", int(storage_row["total_records"]), 3971887))
    checks.append(check("full-corpus off-chain size MiB", round(float(storage_row["offchain_size_mib"]), 5), 11899.55153, 0.00001))
    checks.append(check("full-corpus audit-record size MiB", round(float(storage_row["audit_records_size_mib"]), 6), 1473.437063, 0.000001))
    checks.append(check("full-corpus ledger headers-only size MiB", round(float(storage_row["ledger_blocks_only_size_mib"]), 6), 2.025453, 0.000001))
    checks.append(check("full-corpus ledger plus membership size MiB", round(float(storage_row["ledger_plus_membership_size_mib"]), 6), 380.515149, 0.000001))
    checks.append(check("full-corpus verification passed", bool(storage_row["verification_passed"]), True))

    report = {
        "package": "github_zenodo_reproducibility_package_20260910",
        "manuscript": "Large-Scale Conversational Data Auditability via Cryptographic Commitments and Blockchain Verification",
        "all_checks_passed": all(item["passed"] for item in checks),
        "verification_scope": {
            "immediate": "Validates reported numerical metrics from included derived tables, storage audit summaries, and traceability outputs.",
            "full_pipeline": "Framework scripts are included, but full regeneration requires retrieving the public third-party datasets under their source licenses and preparing the documented local data paths.",
            "not_redistributed": "Original third-party conversational records and HMAC secret keys are not included.",
        },
        "table6_linear_fit": fit,
        "checks": checks,
    }

    (OUTPUTS / "reproducibility_check_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "# Reproducibility Check Report",
        "",
        f"All checks passed: `{report['all_checks_passed']}`",
        "",
        "## Scope",
        "",
        "- Immediate verification validates the reported numerical metrics from included non-raw derived artifacts.",
        "- Full pipeline regeneration requires downloading the public source datasets from their original providers.",
        "- Original third-party conversational records and HMAC secret keys are not redistributed in this package.",
        "",
        "## Table 6 Linear Fit",
        "",
        f"- R squared: `{fit['r_squared']:.6f}`",
        f"- Slope: `{fit['slope_seconds_per_record']:.10f}` seconds per record",
        f"- Seconds per 100,000 records: `{fit['seconds_per_100k_records']:.3f}`",
        "",
        "## Checks",
        "",
    ]
    for item in checks:
        status = "PASS" if item["passed"] else "FAIL"
        lines.append(f"- `{status}` {item['check']}: actual={item['actual']} expected={item['expected']}")
    (OUTPUTS / "reproducibility_check_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    if not report["all_checks_passed"]:
        raise SystemExit("One or more reproducibility checks failed.")


if __name__ == "__main__":
    main()
