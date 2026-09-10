from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import time
from pathlib import Path
from typing import Any, Callable

import pyarrow as pa
import pyarrow.parquet as pq


AUDIT_ROOT = Path(os.environ.get("AUDIT_ROOT", "audit_workspace"))
STAGE_ROOT = AUDIT_ROOT / "12_tampering_simulator"
LEDGER_ROOT = AUDIT_ROOT / "10_blockchain_ledger_simulator" / "02_outputs"
RECORD_ROOT = AUDIT_ROOT / "09_audit_record_generator" / "02_outputs"

SOURCE_LEDGER = LEDGER_ROOT / "ledger_blocks.jsonl"
SOURCE_MEMBERSHIP = LEDGER_ROOT / "ledger_record_membership.parquet"
SOURCE_INTERACTIONS = RECORD_ROOT / "audit_records.parquet"
SOURCE_COMPARISONS = RECORD_ROOT / "comparison_audit_records.parquet"

GENESIS_PREVIOUS_HASH = "0" * 64
BATCH_SIZE = 100000


def ensure_dirs() -> None:
    for sub in ["01_scripts", "02_outputs", "03_reports", "04_logs", "05_documentation", "tampered_cases"]:
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


def write_blocks(path: Path, blocks: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for block in blocks:
            f.write(canonical_json(block) + "\n")


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


def load_membership(path: Path) -> list[dict[str, Any]]:
    rows = []
    pf = pq.ParquetFile(path)
    cols = ["record_id", "decision_hash", "block_id", "position_in_block", "record_group", "record_type", "dataset"]
    for batch in pf.iter_batches(batch_size=BATCH_SIZE, columns=cols):
        rows.extend(batch.to_pylist())
    return rows


def write_membership(path: Path, rows: list[dict[str, Any]]) -> None:
    schema = pa.schema([
        ("record_id", pa.string()),
        ("decision_hash", pa.string()),
        ("block_id", pa.string()),
        ("position_in_block", pa.string()),
        ("record_group", pa.string()),
        ("record_type", pa.string()),
        ("dataset", pa.string()),
    ])
    table = pa.Table.from_pylist([{k: "" if v is None else str(v) for k, v in row.items()} for row in rows], schema=schema)
    pq.write_table(table, path, compression="snappy")


def load_audit_record_index(paths: list[Path]) -> dict[str, dict[str, str]]:
    index = {}
    cols = ["record_id", "decision_hash", "record_type", "dataset"]
    for path in paths:
        pf = pq.ParquetFile(path)
        for batch in pf.iter_batches(batch_size=BATCH_SIZE, columns=cols):
            for row in batch.to_pylist():
                index[row["record_id"]] = row
    return index


def validate_case(ledger_path: Path, membership_path: Path, audit_index: dict[str, dict[str, str]]) -> dict[str, Any]:
    start = time.perf_counter()
    blocks = load_blocks(ledger_path)
    membership_rows = load_membership(membership_path)
    by_block: dict[int, list[dict[str, Any]]] = {}
    for row in membership_rows:
        by_block.setdefault(int(row["block_id"]), []).append(row)
    for block_id in by_block:
        by_block[block_id].sort(key=lambda r: int(r["position_in_block"]))

    errors = []
    previous = GENESIS_PREVIOUS_HASH
    for expected_id, block in enumerate(blocks):
        if block.get("block_id") != expected_id:
            errors.append("block_id_sequence")
        if block.get("previous_block_hash") != previous:
            errors.append("previous_hash_link")
        if recompute_block_hash(block) != block.get("block_hash"):
            errors.append("block_hash")
        rows = by_block.get(block["block_id"], [])
        if len(rows) != block.get("record_count"):
            errors.append("record_count")
        if rows:
            if rows[0]["record_id"] != block.get("first_record_id"):
                errors.append("first_record_id")
            if rows[-1]["record_id"] != block.get("last_record_id"):
                errors.append("last_record_id")
        if merkle_root([r["decision_hash"] for r in rows]) != block.get("merkle_root"):
            errors.append("merkle_root")
        previous = block.get("block_hash")

    for row in membership_rows:
        record = audit_index.get(row["record_id"])
        if not record:
            errors.append("record_exists")
            continue
        if record["decision_hash"] != row["decision_hash"]:
            errors.append("decision_hash_match")
        if record["record_type"] != row["record_type"]:
            errors.append("record_type_match")
        if record["dataset"] != row["dataset"]:
            errors.append("dataset_match")

    elapsed = time.perf_counter() - start
    unique_errors = sorted(set(errors))
    return {
        "detected": bool(unique_errors),
        "error_count": len(errors),
        "unique_error_types": ";".join(unique_errors),
        "detection_time_ms": round(elapsed * 1000, 3),
        "blocks_checked": len(blocks),
        "membership_records_checked": len(membership_rows),
    }


def prepare_case(case_name: str) -> tuple[Path, Path]:
    case_dir = STAGE_ROOT / "tampered_cases" / case_name
    if case_dir.exists():
        shutil.rmtree(case_dir)
    case_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = case_dir / "ledger_blocks.jsonl"
    membership_path = case_dir / "ledger_record_membership.parquet"
    shutil.copy2(SOURCE_LEDGER, ledger_path)
    shutil.copy2(SOURCE_MEMBERSHIP, membership_path)
    return ledger_path, membership_path


def attack_merkle_root(ledger_path: Path, membership_path: Path) -> None:
    blocks = load_blocks(ledger_path)
    blocks[3]["merkle_root"] = "f" * 64
    write_blocks(ledger_path, blocks)


def attack_block_hash(ledger_path: Path, membership_path: Path) -> None:
    blocks = load_blocks(ledger_path)
    blocks[5]["block_hash"] = "a" * 64
    write_blocks(ledger_path, blocks)


def attack_previous_hash(ledger_path: Path, membership_path: Path) -> None:
    blocks = load_blocks(ledger_path)
    blocks[8]["previous_block_hash"] = "b" * 64
    write_blocks(ledger_path, blocks)


def attack_block_reordering(ledger_path: Path, membership_path: Path) -> None:
    blocks = load_blocks(ledger_path)
    blocks[10], blocks[11] = blocks[11], blocks[10]
    write_blocks(ledger_path, blocks)


def attack_decision_hash_membership(ledger_path: Path, membership_path: Path) -> None:
    rows = load_membership(membership_path)
    rows[1234]["decision_hash"] = "c" * 64
    write_membership(membership_path, rows)


def attack_record_deletion(ledger_path: Path, membership_path: Path) -> None:
    rows = load_membership(membership_path)
    del rows[2500]
    write_membership(membership_path, rows)


def attack_record_reassignment(ledger_path: Path, membership_path: Path) -> None:
    rows = load_membership(membership_path)
    rows[4000]["block_id"] = "12"
    rows[4000]["position_in_block"] = "999"
    write_membership(membership_path, rows)


def attack_dataset_label_membership(ledger_path: Path, membership_path: Path) -> None:
    rows = load_membership(membership_path)
    rows[5000]["dataset"] = "tampered_dataset"
    write_membership(membership_path, rows)


ATTACKS: dict[str, Callable[[Path, Path], None]] = {
    "merkle_root_tampering": attack_merkle_root,
    "block_hash_tampering": attack_block_hash,
    "previous_hash_tampering": attack_previous_hash,
    "block_reordering": attack_block_reordering,
    "decision_hash_membership_tampering": attack_decision_hash_membership,
    "record_deletion": attack_record_deletion,
    "record_reassignment": attack_record_reassignment,
    "dataset_label_membership_tampering": attack_dataset_label_membership,
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


def write_report(rows: list[dict[str, Any]]) -> None:
    report = STAGE_ROOT / "03_reports" / "tampering_simulation_report.md"
    detected = sum(1 for r in rows if r["detected"])
    with report.open("w", encoding="utf-8") as f:
        f.write("# Simulador de manipulacion controlada\n\n")
        f.write("Fecha: 2026-06-03\n\n")
        f.write("## Objetivo\n\n")
        f.write("Evaluar si el framework blockchain detecta alteraciones controladas sobre ledger y membresia de registros.\n\n")
        f.write("## Resultados\n\n")
        f.write(f"- Ataques ejecutados: {len(rows)}\n")
        f.write(f"- Ataques detectados: {detected}\n")
        f.write(f"- Tasa de deteccion: {detected / len(rows):.3f}\n\n")
        f.write("| Ataque | Detectado | Tiempo ms | Tipos de error |\n")
        f.write("|---|---|---:|---|\n")
        for row in rows:
            f.write(f"| {row['attack_type']} | {row['detected']} | {row['detection_time_ms']} | {row['unique_error_types']} |\n")
        f.write("\n## Lectura metodologica\n\n")
        f.write("- Las manipulaciones de bloque se detectan mediante hash de bloque y enlaces previos.\n")
        f.write("- Las manipulaciones de registros se detectan mediante Merkle root y cruce contra audit records.\n")
        f.write("- La deteccion no requiere texto original; opera sobre hashes, membresia y metadatos minimos.\n")


def main() -> None:
    ensure_dirs()
    audit_index = load_audit_record_index([SOURCE_INTERACTIONS, SOURCE_COMPARISONS])
    results = []
    for attack_name, attack_fn in ATTACKS.items():
        ledger_path, membership_path = prepare_case(attack_name)
        attack_fn(ledger_path, membership_path)
        validation = validate_case(ledger_path, membership_path, audit_index)
        results.append({
            "attack_type": attack_name,
            **validation,
            "false_acceptance": not validation["detected"],
        })

    write_csv(STAGE_ROOT / "02_outputs" / "tampering_results.csv", results)
    with (STAGE_ROOT / "02_outputs" / "tampering_results.json").open("w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    write_report(results)
    with (STAGE_ROOT / "04_logs" / "tampering_simulator_log.md").open("w", encoding="utf-8") as f:
        f.write("# Log - simulador de manipulacion controlada\n\n")
        f.write("Fecha: 2026-06-03\n\n")
        f.write(f"Ataques ejecutados: {len(results)}\n\n")
        f.write(f"Ataques detectados: {sum(1 for r in results if r['detected'])}\n")
    print(STAGE_ROOT)


if __name__ == "__main__":
    main()
