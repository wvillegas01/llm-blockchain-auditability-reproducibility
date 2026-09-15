# Reproducibility Package

Manuscript: **Large-Scale Conversational Data Auditability via Cryptographic Commitments and Hash-Chained Audit-Ledger Verification**

Package date: 2026-09-10

This repository provides public numerical-audit materials for the results reported in the manuscript. It is designed for public release through GitHub and archival release through Zenodo.

## Reproducibility Scope

The package supports two levels of public verification:

1. **Immediate numerical consistency verification.** The included verification script checks the reported tables and storage metrics against non-raw derived artifacts included in this repository.
2. **Downstream audit-stage traceability.** The included framework scripts document the stages that transform already normalized canonical files into hash-only audit records, lightweight ledger headers, membership mappings, tampering scenarios, and aggregate metrics.

The package does not redistribute original third-party conversational records, HMAC secret keys, or the implementation of the canonical dataset-normalization stage. Users who wish to rerun the complete data-processing workflow must retrieve the public datasets from their original providers, comply with the corresponding source licenses and access conditions, and prepare canonical intermediate files matching the documented schema. The public script `scripts/verify_reported_results.py` should therefore be interpreted as a consistency-checking utility for the released numerical artifacts, not as an end-to-end reproduction of the complete processing pipeline.

## Repository Contents

- `configs/`: experimental configuration and environment metadata.
- `data_access/`: public dataset links and redistribution notes.
- `derived_tables/`: non-raw tables, repeated-run summaries, and aggregate outputs used to verify manuscript results.
- `framework_scripts/`: traceability scripts for audit-record generation, ledger construction, verification, tampering, and performance stages downstream of canonical normalization.
- `reports/`: audit reports supporting the storage-footprint and traceability claims.
- `scripts/verify_reported_results.py`: automated numerical consistency check of the manuscript results against the released derived artifacts.
- `outputs/`: generated verification reports.
- `checksums/`: SHA-256 manifest for the package files.

## Quick Verification

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Run the consistency check:

```bash
python scripts/verify_reported_results.py
```

Expected result:

```text
All checks passed: True
```

The script writes:

- `outputs/reproducibility_check_report.json`
- `outputs/reproducibility_check_report.md`

Regenerate the checksum manifest and release ZIP:

```bash
python scripts/generate_manifest.py
python scripts/build_release_zip.py
```

## Verified Manuscript Results

The consistency-checking script checks:

- fixed 139,258-record pilot set used for hash-mode and tampering experiments;
- SHA-256 and HMAC-SHA-256 verification status;
- repeated SHA-256/HMAC-SHA-256 performance summaries over five executions, including audit-record generation, ledger construction, and full record-set verification;
- eight controlled tampering scenarios and zero false acceptances;
- Table 6 load-scalability metrics over five executions per load configuration and near-linear total-pipeline timing fitted from repeated-run means;
- Table 7 block-size sensitivity metrics over five executions per block-size configuration, interpreted as block-header chain-validation timings and reported in MiB;
- full-corpus storage metrics for 3,971,887 auditable units.

## Public Source Datasets

The study uses the following public datasets:

- LMSYS-Chat-1M: https://huggingface.co/datasets/lmsys/lmsys-chat-1m
- WildChat: https://huggingface.co/datasets/allenai/WildChat
- Chatbot Arena Conversations: https://huggingface.co/datasets/lmsys/chatbot_arena_conversations

Original third-party conversational records are not included in this repository.

## Experimental Environment

The primary experiments reported in the manuscript were executed on an Intel Core i9 workstation with 64 GB RAM, Ubuntu 24.04 LTS, and Python 3.12.

A later local numerical consistency audit was executed on Windows 11 with Python 3.12.3 on a 13th Gen Intel(R) Core(TM) i9-13900HX workstation with 24 physical cores, 32 logical cores, and approximately 31.75 GB RAM. This local audit checked the reported tables against processed project artifacts and does not replace the original experimental environment.

## Data and Security Boundaries

- No original conversational text is redistributed.
- No HMAC secret key is included.
- The implementation of the canonical dataset-normalization stage is not included because it forms part of the potentially commercializable software architecture. The package documents the source datasets, expected canonical outputs, downstream scripts, derived tables, and verification reports needed to evaluate the reported numerical results.
- Derived aggregate tables are included for numerical verification.
- Ledger and audit artifacts are represented through non-raw reports and metrics unless redistribution is compatible with source-dataset constraints.
- Tamper-evidence claims require comparison with preserved artifacts, trusted checkpoints, or externally anchored commitments.

## Citation

Use `CITATION.cff` after the GitHub URL and Zenodo DOI have been assigned.
