# Reproducibility Check Report

All checks passed: `True`

## Scope

- Immediate verification checks the reported numerical metrics against included non-raw derived artifacts and repeated-run summaries.
- This report is a numerical consistency check, not an end-to-end recomputation from the original third-party datasets.
- Full pipeline regeneration requires downloading the public source datasets from their original providers and preparing canonical intermediate files expected by the downstream scripts.
- Original third-party conversational records, HMAC secret keys, and the Stage 08 canonical dataset-normalization implementation are not redistributed in this package.

## Table 6 Linear Fit

- R squared: `0.999960`
- Slope: `0.0001796114` seconds per record
- Seconds per 100,000 records: `17.961`

## Checks

- `PASS` fixed pilot total audit records: actual=139258 expected=139258
- `PASS` fixed pilot interaction records: actual=100000 expected=100000
- `PASS` fixed pilot comparison records: actual=39258 expected=39258
- `PASS` HMAC full record-set verification passed: actual=True expected=True
- `PASS` SHA-256 full record-set verification passed: actual=True expected=True
- `PASS` HMAC false acceptance count: actual=0 expected=0
- `PASS` SHA-256 false acceptance count: actual=0 expected=0
- `PASS` HMAC tampering detection rate: actual=1.0 expected=1.0
- `PASS` SHA-256 tampering detection rate: actual=1.0 expected=1.0
- `PASS` repeated hash-performance SHA-256 runs: actual=5 expected=5
- `PASS` repeated hash-performance HMAC-SHA-256 runs: actual=5 expected=5
- `PASS` repeated SHA-256 verification successes: actual=5 expected=5
- `PASS` repeated HMAC-SHA-256 verification successes: actual=5 expected=5
- `PASS` repeated HMAC audit-generation relative change percent: actual=-14.1418 expected=-14.1418
- `PASS` repeated HMAC full record-set verification relative change percent: actual=0.0124 expected=0.0124
- `PASS` controlled tampering scenarios: actual=8 expected=8
- `PASS` controlled tampering scenarios detected: actual=8 expected=8
- `PASS` controlled tampering false acceptances: actual=0 expected=0
- `PASS` Table 6 repeated load-run count: actual=25 expected=25
- `PASS` Table 6 load scenario count: actual=5 expected=5
- `PASS` Table 6 first scenario audit records: actual=49258 expected=49258
- `PASS` Table 6 last scenario audit records: actual=539258 expected=539258
- `PASS` Table 6 repeated successful verification runs: actual=25 expected=25
- `PASS` Table 6 linear fit R squared from repeated means: actual=0.99996 expected=0.99996
- `PASS` Table 6 seconds per 100k records from repeated means: actual=17.961 expected=17.961
- `PASS` Table 8 final relative latency from repeated means: actual=12.8616 expected=12.8616
- `PASS` Table 7 repeated block-size run count: actual=30 expected=30
- `PASS` Table 7 block-size scenario count: actual=6 expected=6
- `PASS` Table 7 repeated successful validation runs: actual=30 expected=30
- `PASS` Table 7 fixed audit records covered at block size 1000: actual=True expected=True
- `PASS` Table 7 minimum mean block-header chain-validation time: actual=0.00087286 expected=0.00087286
- `PASS` Table 7 maximum mean block-header chain-validation time: actual=0.04202904 expected=0.04202904
- `PASS` full-corpus auditable units: actual=3971887 expected=3971887
- `PASS` full-corpus off-chain size MiB: actual=11899.55153 expected=11899.55153
- `PASS` full-corpus audit-record size MiB: actual=1473.437063 expected=1473.437063
- `PASS` full-corpus ledger headers-only size MiB: actual=2.025453 expected=2.025453
- `PASS` full-corpus ledger plus membership size MiB: actual=380.515149 expected=380.515149
- `PASS` full-corpus verification passed: actual=True expected=True
