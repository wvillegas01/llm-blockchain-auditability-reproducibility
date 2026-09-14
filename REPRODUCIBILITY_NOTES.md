# Reproducibility Notes

This package is intended to address the editorial request that the reported numerical results be reproducible beyond internal project traceability.

## What Can Be Verified Immediately

Running `python scripts/verify_reported_results.py` checks the manuscript's reported numerical results against the included non-raw derived artifacts. This includes hash-mode metrics, tampering detection, Table 6 load scalability, Table 7 block-size sensitivity, and full-corpus storage metrics. The script is a numerical consistency check of the released artifacts rather than an end-to-end recomputation from the original third-party datasets.

## What Requires Dataset Retrieval

Full end-to-end regeneration requires downloading the public third-party datasets listed in `data_access/source_datasets.md` and preparing the canonical intermediate files expected by the downstream framework scripts. The implementation of the canonical dataset-normalization stage is not included in this public package because it forms part of the potentially commercializable software architecture. The original conversational records are not redistributed because they remain subject to the terms of their source repositories.

## Why Raw Data Are Not Included

The study uses public third-party conversational datasets, but public availability does not automatically authorize redistribution in a separate archive. For this reason, the package provides source links, processing scripts, aggregate derived tables, reports, and checksum manifests rather than a copy of the source datasets.

## Editorial Boundary

This repository should be described as a public numerical-audit and consistency-check package containing downstream scripts, configuration files, aggregate outputs, validation reports, and checksum manifests. It should not be described as containing redistributed raw conversational datasets, HMAC secret keys, the Stage 08 canonical normalizer, or a complete end-to-end implementation of the full processing pipeline.
