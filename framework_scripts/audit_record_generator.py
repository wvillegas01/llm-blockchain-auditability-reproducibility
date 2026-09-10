from __future__ import annotations

import argparse
import csv
import hashlib
import hmac
import json
import os
import time
from collections import Counter
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq


AUDIT_ROOT = Path(os.environ.get("AUDIT_ROOT", "audit_workspace"))
STAGE_ROOT = AUDIT_ROOT / "09_audit_record_generator"
NORMALIZED_ROOT = AUDIT_ROOT / "08_canonical_dataset_normalizer" / "02_outputs"

NORMALIZED_INTERACTIONS = NORMALIZED_ROOT / "normalized_interactions.parquet"
NORMALIZED_COMPARISONS = NORMALIZED_ROOT / "normalized_comparisons.parquet"

SCHEMA_VERSION = "audit-record-v1.0"
HASH_MODE_SHA = "sha256"
HASH_MODE_HMAC = "hmac-sha256"
BATCH_SIZE = 20000


INTERACTION_AUDIT_COLUMNS = [
    "record_id",
    "record_sequence",
    "schema_version",
    "record_type",
    "dataset",
    "normalization_id",
    "conversation_id",
    "turn_id",
    "pair_index",
    "model_name",
    "timestamp",
    "timestamp_policy",
    "language",
    "prompt_hash",
    "response_hash",
    "metadata_hash",
    "moderation_hash",
    "decision_hash",
    "hash_algorithm",
]

COMPARISON_AUDIT_COLUMNS = [
    "record_id",
    "record_sequence",
    "schema_version",
    "record_type",
    "dataset",
    "normalization_id",
    "comparison_id",
    "turn_id",
    "pair_index",
    "model_a",
    "model_b",
    "winner",
    "judge",
    "timestamp",
    "timestamp_policy",
    "language",
    "prompt_hash",
    "response_a_hash",
    "response_b_hash",
    "metadata_hash",
    "moderation_hash",
    "decision_hash",
    "hash_algorithm",
]


FORBIDDEN_TEXT_COLUMNS = {
    "prompt",
    "response",
    "response_a",
    "response_b",
    "conversation",
    "conversation_a",
    "conversation_b",
    "content",
    "text",
}


def ensure_dirs() -> None:
    for sub in ["01_scripts", "02_outputs", "03_reports", "04_logs", "05_documentation"]:
        (STAGE_ROOT / sub).mkdir(parents=True, exist_ok=True)


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("\r\n", "\n").replace("\r", "\n").strip()


def digest_text(text: str, secret: str | None = None) -> str:
    data = text.encode("utf-8")
    if secret:
        return hmac.new(secret.encode("utf-8"), data, hashlib.sha256).hexdigest()
    return hashlib.sha256(data).hexdigest()


def digest_object(value: Any, secret: str | None = None) -> str:
    return digest_text(canonical_json(value), secret=secret)


def stable_record_id(*parts: Any, secret: str | None = None) -> str:
    payload = canonical_json([str(p) for p in parts])
    return digest_text(payload, secret=secret)[:32]


def parquet_batches(path: Path, columns: list[str]):
    pf = pq.ParquetFile(path)
    available = set(pf.schema_arrow.names)
    missing = [c for c in columns if c not in available]
    if missing:
        raise ValueError(f"Missing columns in {path}: {missing}")
    yield from pf.iter_batches(batch_size=BATCH_SIZE, columns=columns)


def open_writer(path: Path, columns: list[str]) -> pq.ParquetWriter:
    schema = pa.schema([(col, pa.string()) for col in columns])
    return pq.ParquetWriter(path, schema=schema, compression="snappy")


def write_rows(writer: pq.ParquetWriter, rows: list[dict[str, Any]], columns: list[str]) -> None:
    if not rows:
        return
    table = pa.Table.from_pylist(
        [{col: "" if row.get(col) is None else str(row.get(col)) for col in columns} for row in rows],
        schema=writer.schema,
    )
    writer.write_table(table)


def parse_json_field(value: Any) -> Any:
    if value is None or value == "":
        return None
    try:
        return json.loads(value)
    except Exception:
        return value


def build_interaction_record(row: dict[str, Any], secret: str | None, record_sequence: int) -> dict[str, Any]:
    hash_algorithm = HASH_MODE_HMAC if secret else HASH_MODE_SHA
    metadata_obj = {
        "metadata": parse_json_field(row.get("metadata_json")),
        "dataset": row.get("dataset"),
        "source_normalization_id": row.get("normalization_id"),
        "language": row.get("language"),
        "timestamp_policy": row.get("timestamp_policy"),
    }
    moderation_obj = parse_json_field(row.get("moderation_tag"))
    content_hashes = {
        "prompt_hash": digest_text(normalize_text(row.get("prompt")), secret=secret),
        "response_hash": digest_text(normalize_text(row.get("response")), secret=secret),
        "metadata_hash": digest_object(metadata_obj, secret=secret),
        "moderation_hash": digest_object(moderation_obj, secret=secret),
    }
    base = {
        "schema_version": SCHEMA_VERSION,
        "record_sequence": record_sequence,
        "record_type": "interaction_record",
        "dataset": row.get("dataset"),
        "normalization_id": row.get("normalization_id"),
        "conversation_id": row.get("conversation_id"),
        "turn_id": row.get("turn_id"),
        "pair_index": row.get("pair_index"),
        "model_name": row.get("model_name"),
        "timestamp": row.get("timestamp"),
        "timestamp_policy": row.get("timestamp_policy"),
        "language": row.get("language"),
        **content_hashes,
        "hash_algorithm": hash_algorithm,
    }
    record_id = stable_record_id(
        row.get("dataset"),
        row.get("conversation_id"),
        row.get("turn_id"),
        row.get("pair_index"),
        row.get("model_name"),
        content_hashes["prompt_hash"],
        content_hashes["response_hash"],
        content_hashes["metadata_hash"],
        record_sequence,
        "interaction_record",
        secret=secret,
    )
    decision_payload = {**base, "record_id": record_id}
    return {
        "record_id": record_id,
        **base,
        "decision_hash": digest_object(decision_payload, secret=secret),
    }


def build_comparison_record(row: dict[str, Any], secret: str | None, record_sequence: int) -> dict[str, Any]:
    hash_algorithm = HASH_MODE_HMAC if secret else HASH_MODE_SHA
    metadata_obj = {
        "metadata": parse_json_field(row.get("metadata_json")),
        "dataset": row.get("dataset"),
        "source_normalization_id": row.get("normalization_id"),
        "language": row.get("language"),
        "timestamp_policy": row.get("timestamp_policy"),
    }
    moderation_obj = parse_json_field(row.get("moderation_tag"))
    content_hashes = {
        "prompt_hash": digest_text(normalize_text(row.get("prompt")), secret=secret),
        "response_a_hash": digest_text(normalize_text(row.get("response_a")), secret=secret),
        "response_b_hash": digest_text(normalize_text(row.get("response_b")), secret=secret),
        "metadata_hash": digest_object(metadata_obj, secret=secret),
        "moderation_hash": digest_object(moderation_obj, secret=secret),
    }
    base = {
        "schema_version": SCHEMA_VERSION,
        "record_sequence": record_sequence,
        "record_type": "comparison_record",
        "dataset": row.get("dataset"),
        "normalization_id": row.get("normalization_id"),
        "comparison_id": row.get("comparison_id"),
        "turn_id": row.get("turn_id"),
        "pair_index": row.get("pair_index"),
        "model_a": row.get("model_a"),
        "model_b": row.get("model_b"),
        "winner": row.get("winner"),
        "judge": row.get("judge"),
        "timestamp": row.get("timestamp"),
        "timestamp_policy": row.get("timestamp_policy"),
        "language": row.get("language"),
        **content_hashes,
        "hash_algorithm": hash_algorithm,
    }
    record_id = stable_record_id(
        row.get("dataset"),
        row.get("comparison_id"),
        row.get("turn_id"),
        row.get("pair_index"),
        row.get("model_a"),
        row.get("model_b"),
        content_hashes["prompt_hash"],
        content_hashes["response_a_hash"],
        content_hashes["response_b_hash"],
        content_hashes["metadata_hash"],
        record_sequence,
        "comparison_record",
        secret=secret,
    )
    decision_payload = {**base, "record_id": record_id}
    return {
        "record_id": record_id,
        **base,
        "decision_hash": digest_object(decision_payload, secret=secret),
    }


def generate_records(
    source_path: Path,
    output_path: Path,
    source_columns: list[str],
    output_columns: list[str],
    builder,
    limit: int | None,
    secret: str | None,
) -> dict[str, Any]:
    if output_path.exists():
        output_path.unlink()
    writer = open_writer(output_path, output_columns)
    stats = Counter()
    dataset_counts = Counter()
    hash_algorithm = HASH_MODE_HMAC if secret else HASH_MODE_SHA
    buffer: list[dict[str, Any]] = []
    start = time.perf_counter()
    try:
        for batch in parquet_batches(source_path, source_columns):
            data = batch.to_pylist()
            for row in data:
                record = builder(row, secret, stats["records"])
                buffer.append(record)
                stats["records"] += 1
                dataset_counts[record["dataset"]] += 1
                if len(buffer) >= BATCH_SIZE:
                    write_rows(writer, buffer, output_columns)
                    buffer = []
                if limit and stats["records"] >= limit:
                    break
            if limit and stats["records"] >= limit:
                break
        write_rows(writer, buffer, output_columns)
    finally:
        writer.close()
    elapsed = time.perf_counter() - start
    return {
        "path": str(output_path),
        "records": stats["records"],
        "dataset_counts": dict(dataset_counts),
        "hash_algorithm": hash_algorithm,
        "elapsed_seconds": elapsed,
        "records_per_second": stats["records"] / elapsed if elapsed else 0,
        "size_bytes": output_path.stat().st_size if output_path.exists() else 0,
    }


def inspect_privacy(output_path: Path) -> dict[str, Any]:
    pf = pq.ParquetFile(output_path)
    columns = pf.schema_arrow.names
    forbidden_present = sorted(set(columns) & FORBIDDEN_TEXT_COLUMNS)
    sample_values_with_long_text = 0
    for batch in pf.iter_batches(batch_size=min(1000, pf.metadata.num_rows), columns=columns):
        for row in batch.to_pylist():
            for key, value in row.items():
                if key.endswith("_hash") or key in {"record_id", "decision_hash"}:
                    continue
                if isinstance(value, str) and len(value) > 500:
                    sample_values_with_long_text += 1
        break
    return {
        "path": str(output_path),
        "rows": pf.metadata.num_rows,
        "columns": columns,
        "forbidden_text_columns_present": forbidden_present,
        "sample_values_over_500_chars_non_hash": sample_values_with_long_text,
        "passes_no_text_column_check": len(forbidden_present) == 0,
    }


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


def write_report(summary: dict[str, Any]) -> None:
    report = STAGE_ROOT / "03_reports" / "audit_record_generation_report.md"
    with report.open("w", encoding="utf-8") as f:
        f.write("# Generador de registros auditables para framework blockchain\n\n")
        f.write("Fecha: 2026-06-03\n\n")
        f.write("## Objetivo\n\n")
        f.write("Transformar datos normalizados off-chain en registros auditables sin texto original, aptos para ser insertados en un ledger blockchain ligero.\n\n")
        f.write("## Corrida\n\n")
        f.write(f"- Modo de hash: `{summary['hash_algorithm']}`\n")
        f.write(f"- Limite interacciones: `{summary['limits']['interactions']}`\n")
        f.write(f"- Limite comparaciones: `{summary['limits']['comparisons']}`\n\n")
        f.write("## Resultados\n\n")
        f.write("| Archivo | Registros | Reg/s | MB |\n")
        f.write("|---|---:|---:|---:|\n")
        for key in ["interactions", "comparisons"]:
            item = summary[key]
            f.write(f"| {Path(item['path']).name} | {item['records']} | {item['records_per_second']:.2f} | {item['size_bytes'] / (1024 * 1024):.3f} |\n")
        f.write("\n## Privacidad\n\n")
        f.write("| Archivo | Columnas prohibidas presentes | Pasa chequeo |\n")
        f.write("|---|---|---|\n")
        for item in summary["privacy_checks"]:
            f.write(f"| {Path(item['path']).name} | {item['forbidden_text_columns_present']} | {item['passes_no_text_column_check']} |\n")
        f.write("\n## Decision metodologica\n\n")
        f.write("- Los registros auditables producidos no incluyen columnas `prompt`, `response`, `response_a` ni `response_b`.\n")
        f.write("- Estos archivos son candidatos on-chain/off-chain-minimal para construir bloques, Merkle roots y hashes de bloque.\n")
        f.write("- La siguiente etapa debe construir el ledger blockchain ligero usando `decision_hash` como unidad primaria de inclusión.\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit-interactions", type=int, default=100000)
    parser.add_argument("--limit-comparisons", type=int, default=0, help="0 means all comparisons")
    parser.add_argument("--hash-mode", choices=[HASH_MODE_SHA, HASH_MODE_HMAC], default=HASH_MODE_SHA)
    args = parser.parse_args()

    ensure_dirs()
    secret = None
    if args.hash_mode == HASH_MODE_HMAC:
        secret = os.environ.get("AUDIT_HMAC_SECRET")
        if not secret:
            raise RuntimeError("AUDIT_HMAC_SECRET is required for hmac-sha256 mode.")

    interaction_source_cols = [
        "normalization_id",
        "dataset",
        "conversation_id",
        "turn_id",
        "pair_index",
        "model_name",
        "prompt",
        "response",
        "timestamp",
        "timestamp_policy",
        "language",
        "moderation_tag",
        "metadata_json",
    ]
    comparison_source_cols = [
        "normalization_id",
        "dataset",
        "comparison_id",
        "turn_id",
        "pair_index",
        "model_a",
        "model_b",
        "prompt",
        "response_a",
        "response_b",
        "winner",
        "judge",
        "timestamp",
        "timestamp_policy",
        "language",
        "moderation_tag",
        "metadata_json",
    ]

    interactions_out = STAGE_ROOT / "02_outputs" / "audit_records.parquet"
    comparisons_out = STAGE_ROOT / "02_outputs" / "comparison_audit_records.parquet"
    interaction_summary = generate_records(
        NORMALIZED_INTERACTIONS,
        interactions_out,
        interaction_source_cols,
        INTERACTION_AUDIT_COLUMNS,
        build_interaction_record,
        args.limit_interactions,
        secret,
    )
    comparison_limit = None if args.limit_comparisons == 0 else args.limit_comparisons
    comparison_summary = generate_records(
        NORMALIZED_COMPARISONS,
        comparisons_out,
        comparison_source_cols,
        COMPARISON_AUDIT_COLUMNS,
        build_comparison_record,
        comparison_limit,
        secret,
    )
    privacy_checks = [inspect_privacy(interactions_out), inspect_privacy(comparisons_out)]
    summary = {
        "hash_algorithm": HASH_MODE_HMAC if secret else HASH_MODE_SHA,
        "limits": {
            "interactions": args.limit_interactions,
            "comparisons": "all" if args.limit_comparisons == 0 else args.limit_comparisons,
        },
        "interactions": interaction_summary,
        "comparisons": comparison_summary,
        "privacy_checks": privacy_checks,
    }

    with (STAGE_ROOT / "02_outputs" / "audit_record_generation_summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, default=str)
    write_csv(
        STAGE_ROOT / "02_outputs" / "audit_record_dataset_counts.csv",
        [
            {"record_group": "interactions", "dataset": dataset, "count": count}
            for dataset, count in interaction_summary["dataset_counts"].items()
        ]
        + [
            {"record_group": "comparisons", "dataset": dataset, "count": count}
            for dataset, count in comparison_summary["dataset_counts"].items()
        ],
    )
    write_csv(STAGE_ROOT / "02_outputs" / "privacy_checks.csv", privacy_checks)
    write_report(summary)

    with (STAGE_ROOT / "04_logs" / "audit_record_generation_log.md").open("w", encoding="utf-8") as f:
        f.write("# Log - generador de registros auditables\n\n")
        f.write("Fecha: 2026-06-03\n\n")
        f.write(f"Hash mode: `{summary['hash_algorithm']}`\n\n")
        f.write(f"Interaction records: {interaction_summary['records']}\n\n")
        f.write(f"Comparison records: {comparison_summary['records']}\n\n")
        f.write("Salida principal: `02_outputs/audit_records.parquet` y `02_outputs/comparison_audit_records.parquet`.\n")

    print(STAGE_ROOT)


if __name__ == "__main__":
    main()
