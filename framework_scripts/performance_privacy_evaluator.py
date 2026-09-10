from __future__ import annotations

import csv
import json
import os
import time
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq


AUDIT_ROOT = Path(os.environ.get("AUDIT_ROOT", "audit_workspace"))
STAGE_ROOT = AUDIT_ROOT / "13_performance_privacy_evaluator"

NORMALIZER_ROOT = AUDIT_ROOT / "08_canonical_dataset_normalizer" / "02_outputs"
AUDIT_RECORD_ROOT = AUDIT_ROOT / "09_audit_record_generator" / "02_outputs"
LEDGER_ROOT = AUDIT_ROOT / "10_blockchain_ledger_simulator" / "02_outputs"
VERIFY_ROOT = AUDIT_ROOT / "11_cryptographic_integrity_verifier" / "02_outputs"
TAMPER_ROOT = AUDIT_ROOT / "12_tampering_simulator" / "02_outputs"


def ensure_dirs() -> None:
    for sub in ["01_scripts", "02_outputs", "03_reports", "04_logs", "05_documentation"]:
        (STAGE_ROOT / sub).mkdir(parents=True, exist_ok=True)


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def file_size(path: Path) -> int:
    return path.stat().st_size if path.exists() else 0


def parquet_rows(path: Path) -> int:
    return pq.ParquetFile(path).metadata.num_rows if path.exists() else 0


def parquet_columns(path: Path) -> list[str]:
    return pq.ParquetFile(path).schema_arrow.names if path.exists() else []


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def mb(value: int | float) -> float:
    return round(float(value) / (1024 * 1024), 6)


def collect_storage_metrics() -> list[dict[str, Any]]:
    files = [
        ("offchain", "normalized_interactions", NORMALIZER_ROOT / "normalized_interactions.parquet"),
        ("offchain", "normalized_comparisons", NORMALIZER_ROOT / "normalized_comparisons.parquet"),
        ("audit_records", "audit_records", AUDIT_RECORD_ROOT / "audit_records.parquet"),
        ("audit_records", "comparison_audit_records", AUDIT_RECORD_ROOT / "comparison_audit_records.parquet"),
        ("ledger", "ledger_blocks", LEDGER_ROOT / "ledger_blocks.jsonl"),
        ("ledger", "ledger_record_membership", LEDGER_ROOT / "ledger_record_membership.parquet"),
    ]
    rows = []
    for category, name, path in files:
        rows.append({
            "category": category,
            "artifact": name,
            "path": str(path),
            "rows": parquet_rows(path) if path.suffix == ".parquet" else "",
            "size_bytes": file_size(path),
            "size_mb": mb(file_size(path)),
            "columns": ";".join(parquet_columns(path)) if path.suffix == ".parquet" else "",
        })
    return rows


def collect_performance_metrics() -> list[dict[str, Any]]:
    audit_summary = load_json(AUDIT_RECORD_ROOT / "audit_record_generation_summary.json")
    ledger_summary = load_json(LEDGER_ROOT / "ledger_build_summary.json")
    verify_summary = load_json(VERIFY_ROOT / "cryptographic_integrity_summary.json")
    tamper_results = []
    tamper_csv = TAMPER_ROOT / "tampering_results.csv"
    with tamper_csv.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            tamper_results.append(row)
    avg_tamper_ms = sum(float(r["detection_time_ms"]) for r in tamper_results) / len(tamper_results)

    return [
        {
            "stage": "audit_record_generation_interactions",
            "records": audit_summary["interactions"]["records"],
            "elapsed_seconds": audit_summary["interactions"]["elapsed_seconds"],
            "throughput_records_per_second": audit_summary["interactions"]["records_per_second"],
            "notes": "prompt-response audit records",
        },
        {
            "stage": "audit_record_generation_comparisons",
            "records": audit_summary["comparisons"]["records"],
            "elapsed_seconds": audit_summary["comparisons"]["elapsed_seconds"],
            "throughput_records_per_second": audit_summary["comparisons"]["records_per_second"],
            "notes": "A/B comparison audit records",
        },
        {
            "stage": "ledger_build",
            "records": ledger_summary["summary"]["record_count"],
            "elapsed_seconds": ledger_summary["summary"]["elapsed_seconds"],
            "throughput_records_per_second": ledger_summary["summary"]["records_per_second"],
            "notes": f"{ledger_summary['summary']['block_count']} blocks",
        },
        {
            "stage": "cryptographic_integrity_verification",
            "records": verify_summary["membership_records"],
            "elapsed_seconds": verify_summary["elapsed_seconds"],
            "throughput_records_per_second": verify_summary["membership_records"] / verify_summary["elapsed_seconds"],
            "notes": "chain, Merkle, sampled crosscheck",
        },
        {
            "stage": "tampering_detection_average",
            "records": tamper_results[0]["membership_records_checked"] if tamper_results else "",
            "elapsed_seconds": avg_tamper_ms / 1000,
            "throughput_records_per_second": float(tamper_results[0]["membership_records_checked"]) / (avg_tamper_ms / 1000) if tamper_results else "",
            "notes": "average per attack scenario",
        },
    ]


def collect_privacy_metrics(storage_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    offchain_interactions = NORMALIZER_ROOT / "normalized_interactions.parquet"
    offchain_comparisons = NORMALIZER_ROOT / "normalized_comparisons.parquet"
    audit_records = AUDIT_RECORD_ROOT / "audit_records.parquet"
    comparison_records = AUDIT_RECORD_ROOT / "comparison_audit_records.parquet"
    ledger = LEDGER_ROOT / "ledger_blocks.jsonl"
    membership = LEDGER_ROOT / "ledger_record_membership.parquet"

    text_columns = {"prompt", "response", "response_a", "response_b"}
    audit_cols = set(parquet_columns(audit_records))
    comp_cols = set(parquet_columns(comparison_records))
    offchain_text_cols = sorted((set(parquet_columns(offchain_interactions)) | set(parquet_columns(offchain_comparisons))) & text_columns)
    audit_text_cols = sorted((audit_cols | comp_cols) & text_columns)

    offchain_size = file_size(offchain_interactions) + file_size(offchain_comparisons)
    audit_size = file_size(audit_records) + file_size(comparison_records)
    ledger_size = file_size(ledger) + file_size(membership)
    chain_minimal_size = file_size(ledger)

    return [
        {
            "metric": "offchain_text_columns_present",
            "value": ";".join(offchain_text_cols),
            "interpretation": "Text retained only in off-chain normalized repository",
        },
        {
            "metric": "audit_record_text_columns_present",
            "value": ";".join(audit_text_cols),
            "interpretation": "Must be empty for privacy-preserving audit records",
        },
        {
            "metric": "offchain_repository_size_mb",
            "value": mb(offchain_size),
            "interpretation": "Normalized data with original text",
        },
        {
            "metric": "audit_records_size_mb",
            "value": mb(audit_size),
            "interpretation": "Hash-only audit records for pilot",
        },
        {
            "metric": "ledger_plus_membership_size_mb",
            "value": mb(ledger_size),
            "interpretation": "Blockchain ledger plus membership mapping",
        },
        {
            "metric": "ledger_blocks_only_size_mb",
            "value": mb(chain_minimal_size),
            "interpretation": "On-chain-like block header footprint",
        },
        {
            "metric": "audit_record_storage_reduction_vs_offchain_pct",
            "value": round((1 - audit_size / offchain_size) * 100, 6) if offchain_size else "",
            "interpretation": "Storage reduction from text-bearing off-chain repository to hash-only audit records",
        },
        {
            "metric": "ledger_blocks_storage_reduction_vs_offchain_pct",
            "value": round((1 - chain_minimal_size / offchain_size) * 100, 6) if offchain_size else "",
            "interpretation": "Storage reduction for ledger block headers only",
        },
    ]


def collect_tampering_metrics() -> list[dict[str, Any]]:
    rows = []
    with (TAMPER_ROOT / "tampering_results.csv").open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            rows.append(row)
    detected = sum(1 for r in rows if r["detected"] == "True")
    return [
        {
            "metric": "tampering_attack_count",
            "value": len(rows),
        },
        {
            "metric": "tampering_detected_count",
            "value": detected,
        },
        {
            "metric": "tampering_detection_rate",
            "value": detected / len(rows) if rows else "",
        },
        {
            "metric": "false_acceptance_count",
            "value": sum(1 for r in rows if r["false_acceptance"] == "True"),
        },
        {
            "metric": "mean_detection_time_ms",
            "value": round(sum(float(r["detection_time_ms"]) for r in rows) / len(rows), 6) if rows else "",
        },
    ]


def write_report(storage_rows, performance_rows, privacy_rows, tamper_rows) -> None:
    report = STAGE_ROOT / "03_reports" / "performance_privacy_evaluation_report.md"
    with report.open("w", encoding="utf-8") as f:
        f.write("# Evaluacion de rendimiento y privacidad\n\n")
        f.write("Fecha: 2026-06-03\n\n")
        f.write("## Objetivo\n\n")
        f.write("Consolidar metricas experimentales del framework blockchain aplicado a trazabilidad verificable de decisiones LLM.\n\n")
        f.write("## Rendimiento\n\n")
        f.write("| Etapa | Registros | Segundos | Throughput reg/s |\n")
        f.write("|---|---:|---:|---:|\n")
        for row in performance_rows:
            f.write(f"| {row['stage']} | {row['records']} | {float(row['elapsed_seconds']):.6f} | {float(row['throughput_records_per_second']):.2f} |\n")
        f.write("\n## Almacenamiento\n\n")
        f.write("| Categoria | Artefacto | Filas | MB |\n")
        f.write("|---|---|---:|---:|\n")
        for row in storage_rows:
            f.write(f"| {row['category']} | {row['artifact']} | {row['rows']} | {row['size_mb']} |\n")
        f.write("\n## Privacidad\n\n")
        f.write("| Metrica | Valor | Interpretacion |\n")
        f.write("|---|---:|---|\n")
        for row in privacy_rows:
            f.write(f"| {row['metric']} | {row['value']} | {row['interpretation']} |\n")
        f.write("\n## Manipulacion\n\n")
        f.write("| Metrica | Valor |\n")
        f.write("|---|---:|\n")
        for row in tamper_rows:
            f.write(f"| {row['metric']} | {row['value']} |\n")
        f.write("\n## Lectura metodologica\n\n")
        f.write("- La arquitectura separa repositorio off-chain con texto y registros auditables hash-only.\n")
        f.write("- El ledger minimo mantiene solo encabezados de bloque, Merkle roots y enlaces criptograficos.\n")
        f.write("- La evaluacion piloto ya permite reportar throughput, almacenamiento, privacidad y deteccion de manipulacion.\n")
        f.write("- Para resultados finales del articulo, estas mismas metricas deben repetirse por volumen: 10k, 50k, 100k, 250k y 500k.\n")


def main() -> None:
    start = time.perf_counter()
    ensure_dirs()
    storage_rows = collect_storage_metrics()
    performance_rows = collect_performance_metrics()
    privacy_rows = collect_privacy_metrics(storage_rows)
    tamper_rows = collect_tampering_metrics()

    write_csv(STAGE_ROOT / "02_outputs" / "storage_metrics.csv", storage_rows)
    write_csv(STAGE_ROOT / "02_outputs" / "performance_metrics.csv", performance_rows)
    write_csv(STAGE_ROOT / "02_outputs" / "privacy_metrics.csv", privacy_rows)
    write_csv(STAGE_ROOT / "02_outputs" / "tampering_summary_metrics.csv", tamper_rows)
    summary = {
        "storage_metrics": storage_rows,
        "performance_metrics": performance_rows,
        "privacy_metrics": privacy_rows,
        "tampering_metrics": tamper_rows,
    }
    with (STAGE_ROOT / "02_outputs" / "performance_privacy_summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, default=str)
    write_report(storage_rows, performance_rows, privacy_rows, tamper_rows)
    elapsed = time.perf_counter() - start
    with (STAGE_ROOT / "04_logs" / "performance_privacy_evaluator_log.md").open("w", encoding="utf-8") as f:
        f.write("# Log - evaluador de rendimiento y privacidad\n\n")
        f.write("Fecha: 2026-06-03\n\n")
        f.write(f"Tiempo de ejecucion: {elapsed:.3f} segundos\n")
    print(STAGE_ROOT)


if __name__ == "__main__":
    main()
