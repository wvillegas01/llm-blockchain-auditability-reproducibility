from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
import pyarrow as pa


AUDIT_ROOT = Path(os.environ.get("AUDIT_ROOT", "audit_workspace"))
STAGE_ROOT = AUDIT_ROOT / "10_blockchain_ledger_simulator"
RECORD_ROOT = AUDIT_ROOT / "09_audit_record_generator" / "02_outputs"

INTERACTION_RECORDS = RECORD_ROOT / "audit_records.parquet"
COMPARISON_RECORDS = RECORD_ROOT / "comparison_audit_records.parquet"

LEDGER_VERSION = "lightweight-ledger-v1.0"
GENESIS_PREVIOUS_HASH = "0" * 64
BATCH_SIZE = 50000


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


def iter_records(path: Path, record_group: str):
    pf = pq.ParquetFile(path)
    cols = ["record_id", "record_type", "dataset", "timestamp", "decision_hash", "hash_algorithm"]
    for batch in pf.iter_batches(batch_size=BATCH_SIZE, columns=cols):
        for row in batch.to_pylist():
            yield {
                "record_group": record_group,
                "record_id": row["record_id"],
                "record_type": row["record_type"],
                "dataset": row["dataset"],
                "timestamp": row["timestamp"],
                "decision_hash": row["decision_hash"],
                "hash_algorithm": row["hash_algorithm"],
            }


def build_block(block_id: int, previous_hash: str, records: list[dict[str, Any]], started_at: float) -> dict[str, Any]:
    decision_hashes = [r["decision_hash"] for r in records]
    record_ids = [r["record_id"] for r in records]
    datasets: dict[str, int] = {}
    record_types: dict[str, int] = {}
    for record in records:
        datasets[record["dataset"]] = datasets.get(record["dataset"], 0) + 1
        record_types[record["record_type"]] = record_types.get(record["record_type"], 0) + 1
    root = merkle_root(decision_hashes)
    block_payload = {
        "ledger_version": LEDGER_VERSION,
        "block_id": block_id,
        "previous_block_hash": previous_hash,
        "record_count": len(records),
        "first_record_id": record_ids[0],
        "last_record_id": record_ids[-1],
        "merkle_root": root,
        "datasets": datasets,
        "record_types": record_types,
    }
    block_hash = hash_object(block_payload)
    return {
        **block_payload,
        "block_hash": block_hash,
        "build_elapsed_ms": round((time.perf_counter() - started_at) * 1000, 3),
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(canonical_json(row) + "\n")


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


def build_ledger(block_size: int) -> dict[str, Any]:
    ledger_path = STAGE_ROOT / "02_outputs" / "ledger_blocks.jsonl"
    membership_path = STAGE_ROOT / "02_outputs" / "ledger_record_membership.parquet"
    if ledger_path.exists():
        ledger_path.unlink()
    if membership_path.exists():
        membership_path.unlink()

    records_iter = (
        list(iter_records(INTERACTION_RECORDS, "interactions"))
        + list(iter_records(COMPARISON_RECORDS, "comparisons"))
    )
    blocks: list[dict[str, Any]] = []
    membership_rows: list[dict[str, str]] = []
    previous_hash = GENESIS_PREVIOUS_HASH
    total_records = 0
    start = time.perf_counter()

    for offset in range(0, len(records_iter), block_size):
        block_records = records_iter[offset : offset + block_size]
        block_id = len(blocks)
        block_started = time.perf_counter()
        block = build_block(block_id, previous_hash, block_records, block_started)
        blocks.append(block)
        previous_hash = block["block_hash"]
        total_records += len(block_records)
        for idx, record in enumerate(block_records):
            membership_rows.append({
                "record_id": record["record_id"],
                "decision_hash": record["decision_hash"],
                "block_id": str(block_id),
                "position_in_block": str(idx),
                "record_group": record["record_group"],
                "record_type": record["record_type"],
                "dataset": record["dataset"],
            })

    write_jsonl(ledger_path, blocks)
    table = pa.Table.from_pylist(membership_rows)
    pq.write_table(table, membership_path, compression="snappy")
    elapsed = time.perf_counter() - start
    return {
        "ledger_path": str(ledger_path),
        "membership_path": str(membership_path),
        "block_size": block_size,
        "block_count": len(blocks),
        "record_count": total_records,
        "elapsed_seconds": elapsed,
        "records_per_second": total_records / elapsed if elapsed else 0,
        "final_block_hash": blocks[-1]["block_hash"] if blocks else "",
        "ledger_size_bytes": ledger_path.stat().st_size if ledger_path.exists() else 0,
        "membership_size_bytes": membership_path.stat().st_size if membership_path.exists() else 0,
    }


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


def validate_ledger(ledger_path: Path) -> dict[str, Any]:
    blocks = load_blocks(ledger_path)
    errors: list[str] = []
    previous_hash = GENESIS_PREVIOUS_HASH
    for expected_id, block in enumerate(blocks):
        if block.get("block_id") != expected_id:
            errors.append(f"block_id_mismatch:{expected_id}")
        if block.get("previous_block_hash") != previous_hash:
            errors.append(f"previous_hash_mismatch:{expected_id}")
        recomputed = recompute_block_hash(block)
        if recomputed != block.get("block_hash"):
            errors.append(f"block_hash_mismatch:{expected_id}")
        previous_hash = block.get("block_hash")
    return {
        "blocks_validated": len(blocks),
        "errors": errors,
        "is_valid": len(errors) == 0,
        "final_block_hash": blocks[-1]["block_hash"] if blocks else "",
    }


def write_report(summary: dict[str, Any], validation: dict[str, Any]) -> None:
    report = STAGE_ROOT / "03_reports" / "blockchain_ledger_simulator_report.md"
    with report.open("w", encoding="utf-8") as f:
        f.write("# Simulador de ledger blockchain ligero\n\n")
        f.write("Fecha: 2026-06-03\n\n")
        f.write("## Objetivo\n\n")
        f.write("Construir un ledger criptograficamente encadenado a partir de registros auditables sin texto original.\n\n")
        f.write("## Configuracion\n\n")
        f.write(f"- Version de ledger: `{LEDGER_VERSION}`\n")
        f.write(f"- Tamano de bloque: `{summary['block_size']}` registros\n")
        f.write(f"- Hash genesis: `{GENESIS_PREVIOUS_HASH}`\n\n")
        f.write("## Resultados\n\n")
        f.write(f"- Registros incluidos: {summary['record_count']}\n")
        f.write(f"- Bloques generados: {summary['block_count']}\n")
        f.write(f"- Throughput de construccion: {summary['records_per_second']:.2f} registros/s\n")
        f.write(f"- Hash final: `{summary['final_block_hash']}`\n")
        f.write(f"- Tamano ledger JSONL: {summary['ledger_size_bytes'] / (1024 * 1024):.3f} MB\n")
        f.write(f"- Tamano membresia Parquet: {summary['membership_size_bytes'] / (1024 * 1024):.3f} MB\n\n")
        f.write("## Validacion\n\n")
        f.write(f"- Bloques validados: {validation['blocks_validated']}\n")
        f.write(f"- Ledger valido: {validation['is_valid']}\n")
        f.write(f"- Errores: `{validation['errors']}`\n\n")
        f.write("## Lectura metodologica\n\n")
        f.write("- El ledger usa `decision_hash` como unidad primaria de inclusion.\n")
        f.write("- Cada bloque resume sus registros mediante Merkle root.\n")
        f.write("- Cada bloque queda enlazado al anterior mediante `previous_block_hash`.\n")
        f.write("- Esta etapa no implementa consenso distribuido; simula la capa criptografica necesaria para evaluar auditabilidad, integridad y tamper detection.\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--block-size", type=int, default=1000)
    args = parser.parse_args()

    ensure_dirs()
    summary = build_ledger(args.block_size)
    validation = validate_ledger(Path(summary["ledger_path"]))

    with (STAGE_ROOT / "02_outputs" / "ledger_build_summary.json").open("w", encoding="utf-8") as f:
        json.dump({"summary": summary, "validation": validation}, f, ensure_ascii=False, indent=2)
    write_csv(STAGE_ROOT / "02_outputs" / "ledger_validation_results.csv", [validation])
    write_report(summary, validation)

    with (STAGE_ROOT / "04_logs" / "blockchain_ledger_simulator_log.md").open("w", encoding="utf-8") as f:
        f.write("# Log - simulador de ledger blockchain ligero\n\n")
        f.write("Fecha: 2026-06-03\n\n")
        f.write(f"Block size: {args.block_size}\n\n")
        f.write(f"Records: {summary['record_count']}\n\n")
        f.write(f"Blocks: {summary['block_count']}\n\n")
        f.write(f"Valid: {validation['is_valid']}\n")
    print(STAGE_ROOT)


if __name__ == "__main__":
    main()
