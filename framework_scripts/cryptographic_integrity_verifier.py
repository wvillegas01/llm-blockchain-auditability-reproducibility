from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq


AUDIT_ROOT = Path(os.environ.get("AUDIT_ROOT", "audit_workspace"))
STAGE_ROOT = AUDIT_ROOT / "11_cryptographic_integrity_verifier"
LEDGER_ROOT = AUDIT_ROOT / "10_blockchain_ledger_simulator" / "02_outputs"
RECORD_ROOT = AUDIT_ROOT / "09_audit_record_generator" / "02_outputs"

LEDGER_BLOCKS = LEDGER_ROOT / "ledger_blocks.jsonl"
LEDGER_MEMBERSHIP = LEDGER_ROOT / "ledger_record_membership.parquet"
INTERACTION_RECORDS = RECORD_ROOT / "audit_records.parquet"
COMPARISON_RECORDS = RECORD_ROOT / "comparison_audit_records.parquet"

GENESIS_PREVIOUS_HASH = "0" * 64
BATCH_SIZE = 100000


def ensure_dirs() -> None:
    for sub in ["01_scripts", "02_outputs", "03_reports", "04_logs", "05_documentation"]:
        (STAGE_ROOT / sub).mkdir(parents=True, exist_ok=True)


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def hash_object(value: Any) -> str:
    return sha256_text(canonical_json(value))


def merkle_root(hashes: list[str]) -> str:
    if not hashes:
        return sha256_text("")
    level = list(hashes)
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])
        level = [sha256_text(level[i] + level[i + 1]) for i in range(0, len(level), 2)]
    return level[0]


def load_blocks(path: Path) -> list[dict[str, Any]]:
    blocks = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                blocks.append(json.loads(line))
    return blocks


def recompute_block_hash(block: dict[str, Any]) -> str:
    payload = {
        "ledger_version": block["ledger_version"],
        "block_id": block["block_id"],
        "previous_block_hash": block["previous_block_hash"],
        "record_count": block["record_count"],
        "first_record_id": block["first_record_id"],
        "last_record_id": block["last_record_id"],
        "merkle_root": block["merkle_root"],
        "datasets": block["datasets"],
        "record_types": block["record_types"],
    }
    return hash_object(payload)


def load_membership(path: Path) -> dict[int, list[dict[str, Any]]]:
    by_block: dict[int, list[dict[str, Any]]] = defaultdict(list)
    pf = pq.ParquetFile(path)
    cols = ["record_id", "decision_hash", "block_id", "position_in_block", "record_group", "record_type", "dataset"]
    for batch in pf.iter_batches(batch_size=BATCH_SIZE, columns=cols):
        for row in batch.to_pylist():
            by_block[int(row["block_id"])].append(row)
    for block_id in by_block:
        by_block[block_id].sort(key=lambda r: int(r["position_in_block"]))
    return by_block


def load_audit_record_index(paths: list[Path]) -> dict[str, dict[str, str]]:
    index: dict[str, dict[str, str]] = {}
    cols = ["record_id", "decision_hash", "record_type", "dataset"]
    for path in paths:
        pf = pq.ParquetFile(path)
        for batch in pf.iter_batches(batch_size=BATCH_SIZE, columns=cols):
            for row in batch.to_pylist():
                index[row["record_id"]] = row
    return index


def validate_chain(blocks: list[dict[str, Any]]) -> dict[str, Any]:
    errors = []
    previous = GENESIS_PREVIOUS_HASH
    for expected_id, block in enumerate(blocks):
        if block.get("block_id") != expected_id:
            errors.append({"check": "block_id_sequence", "block_id": expected_id})
        if block.get("previous_block_hash") != previous:
            errors.append({"check": "previous_hash_link", "block_id": expected_id})
        recomputed = recompute_block_hash(block)
        if recomputed != block.get("block_hash"):
            errors.append({"check": "block_hash", "block_id": expected_id, "expected": recomputed, "observed": block.get("block_hash")})
        previous = block.get("block_hash")
    return {
        "check": "chain_validation",
        "items_checked": len(blocks),
        "errors": errors,
        "passed": len(errors) == 0,
    }


def validate_merkle_and_membership(blocks: list[dict[str, Any]], by_block: dict[int, list[dict[str, Any]]]) -> dict[str, Any]:
    errors = []
    total_records = 0
    dataset_counts = Counter()
    record_type_counts = Counter()
    for block in blocks:
        block_id = block["block_id"]
        rows = by_block.get(block_id, [])
        total_records += len(rows)
        if len(rows) != block["record_count"]:
            errors.append({"check": "record_count", "block_id": block_id, "expected": block["record_count"], "observed": len(rows)})
        if rows:
            if rows[0]["record_id"] != block["first_record_id"]:
                errors.append({"check": "first_record_id", "block_id": block_id})
            if rows[-1]["record_id"] != block["last_record_id"]:
                errors.append({"check": "last_record_id", "block_id": block_id})
        computed_root = merkle_root([r["decision_hash"] for r in rows])
        if computed_root != block["merkle_root"]:
            errors.append({"check": "merkle_root", "block_id": block_id, "expected": computed_root, "observed": block["merkle_root"]})
        for row in rows:
            dataset_counts[row["dataset"]] += 1
            record_type_counts[row["record_type"]] += 1
    return {
        "check": "merkle_and_membership_validation",
        "items_checked": total_records,
        "block_count": len(blocks),
        "dataset_counts": dict(dataset_counts),
        "record_type_counts": dict(record_type_counts),
        "errors": errors,
        "passed": len(errors) == 0,
    }


def validate_against_audit_records(by_block: dict[int, list[dict[str, Any]]], audit_index: dict[str, dict[str, str]], sample_size: int) -> dict[str, Any]:
    all_memberships = [row for rows in by_block.values() for row in rows]
    if sample_size and sample_size < len(all_memberships):
        rng = random.Random(20260603)
        sample = rng.sample(all_memberships, sample_size)
    else:
        sample = all_memberships
    errors = []
    for row in sample:
        record = audit_index.get(row["record_id"])
        if not record:
            errors.append({"check": "record_exists", "record_id": row["record_id"]})
            continue
        if record["decision_hash"] != row["decision_hash"]:
            errors.append({"check": "decision_hash_match", "record_id": row["record_id"]})
        if record["record_type"] != row["record_type"]:
            errors.append({"check": "record_type_match", "record_id": row["record_id"]})
        if record["dataset"] != row["dataset"]:
            errors.append({"check": "dataset_match", "record_id": row["record_id"]})
    return {
        "check": "audit_record_membership_crosscheck",
        "items_checked": len(sample),
        "population_size": len(all_memberships),
        "sample_size": sample_size if sample_size else "all",
        "errors": errors,
        "passed": len(errors) == 0,
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
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


def flatten_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for result in results:
        rows.append({
            "check": result["check"],
            "passed": result["passed"],
            "items_checked": result.get("items_checked", ""),
            "block_count": result.get("block_count", ""),
            "error_count": len(result.get("errors", [])),
        })
    return rows


def write_report(summary: dict[str, Any]) -> None:
    report = STAGE_ROOT / "03_reports" / "cryptographic_integrity_verification_report.md"
    with report.open("w", encoding="utf-8") as f:
        f.write("# Verificacion criptografica e integridad del ledger\n\n")
        f.write("Fecha: 2026-06-03\n\n")
        f.write("## Objetivo\n\n")
        f.write("Verificar que el ledger blockchain ligero conserva integridad criptografica, encadenamiento de bloques, Merkle roots y membresia de registros.\n\n")
        f.write("## Resultados\n\n")
        f.write("| Check | Pasa | Items revisados | Errores |\n")
        f.write("|---|---|---:|---:|\n")
        for result in summary["results"]:
            f.write(f"| {result['check']} | {result['passed']} | {result.get('items_checked', '')} | {len(result.get('errors', []))} |\n")
        f.write("\n## Metricas\n\n")
        f.write(f"- Tiempo total: {summary['elapsed_seconds']:.3f} segundos\n")
        f.write(f"- Bloques cargados: {summary['block_count']}\n")
        f.write(f"- Registros en membresia: {summary['membership_records']}\n")
        f.write(f"- Registros auditables indexados: {summary['audit_records_indexed']}\n")
        f.write(f"- Verificacion global: {summary['overall_passed']}\n\n")
        f.write("## Lectura metodologica\n\n")
        f.write("- La verificacion confirma que el ledger puede auditarse sin acceder al texto original.\n")
        f.write("- La membresia se comprueba mediante `record_id` y `decision_hash`.\n")
        f.write("- Los Merkle roots se recalculan desde los `decision_hash` asociados a cada bloque.\n")
        f.write("- La siguiente etapa puede introducir manipulaciones controladas para medir deteccion.\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample-records", type=int, default=50000)
    args = parser.parse_args()

    ensure_dirs()
    start = time.perf_counter()
    blocks = load_blocks(LEDGER_BLOCKS)
    by_block = load_membership(LEDGER_MEMBERSHIP)
    audit_index = load_audit_record_index([INTERACTION_RECORDS, COMPARISON_RECORDS])

    chain_result = validate_chain(blocks)
    merkle_result = validate_merkle_and_membership(blocks, by_block)
    crosscheck_result = validate_against_audit_records(by_block, audit_index, args.sample_records)
    results = [chain_result, merkle_result, crosscheck_result]
    elapsed = time.perf_counter() - start
    membership_records = sum(len(rows) for rows in by_block.values())
    summary = {
        "elapsed_seconds": elapsed,
        "block_count": len(blocks),
        "membership_records": membership_records,
        "audit_records_indexed": len(audit_index),
        "overall_passed": all(result["passed"] for result in results),
        "results": results,
    }

    with (STAGE_ROOT / "02_outputs" / "cryptographic_integrity_summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, default=str)
    write_csv(STAGE_ROOT / "02_outputs" / "cryptographic_integrity_results.csv", flatten_results(results))
    all_errors = []
    for result in results:
        for error in result.get("errors", []):
            all_errors.append({"check": result["check"], **error})
    write_csv(STAGE_ROOT / "02_outputs" / "cryptographic_integrity_errors.csv", all_errors)
    write_report(summary)

    with (STAGE_ROOT / "04_logs" / "cryptographic_integrity_verifier_log.md").open("w", encoding="utf-8") as f:
        f.write("# Log - verificador criptografico de integridad\n\n")
        f.write("Fecha: 2026-06-03\n\n")
        f.write(f"Sample records: {args.sample_records}\n\n")
        f.write(f"Overall passed: {summary['overall_passed']}\n\n")
        f.write(f"Elapsed seconds: {elapsed:.3f}\n")
    print(STAGE_ROOT)


if __name__ == "__main__":
    main()
