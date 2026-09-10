# Reproducibility Check Report

All checks passed: `True`

## Scope

- Immediate verification validates the reported numerical metrics from included non-raw derived artifacts.
- Full pipeline regeneration requires downloading the public source datasets from their original providers.
- Original third-party conversational records and HMAC secret keys are not redistributed in this package.

## Table 6 Linear Fit

- R squared: `0.999989`
- Slope: `0.0000839245` seconds per record
- Seconds per 100,000 records: `8.392`

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
- `PASS` HMAC audit-generation relative change percent: actual=-5.3731 expected=-5.3731
- `PASS` HMAC full record-set verification relative change percent: actual=3.2635 expected=3.2635
- `PASS` controlled tampering scenarios: actual=8 expected=8
- `PASS` controlled tampering scenarios detected: actual=8 expected=8
- `PASS` controlled tampering false acceptances: actual=0 expected=0
- `PASS` Table 6 load scenario count: actual=5 expected=5
- `PASS` Table 6 first scenario audit records: actual=49258 expected=49258
- `PASS` Table 6 last scenario audit records: actual=539258 expected=539258
- `PASS` Table 6 linear fit R squared: actual=0.999989 expected=0.999989
- `PASS` Table 6 seconds per 100k records: actual=8.392 expected=8.392
- `PASS` Table 6 final relative latency: actual=8.9185 expected=8.9185
- `PASS` Table 7 block-size scenario count: actual=6 expected=6
- `PASS` Table 7 fixed audit records covered at block size 1000: actual=True expected=True
- `PASS` Table 7 minimum block-header chain-validation time: actual=2.6e-05 expected=2.6e-05
- `PASS` Table 7 maximum block-header chain-validation time: actual=0.000921 expected=0.000921
- `PASS` full-corpus auditable units: actual=3971887 expected=3971887
- `PASS` full-corpus off-chain size MiB: actual=11899.55153 expected=11899.55153
- `PASS` full-corpus audit-record size MiB: actual=1473.437063 expected=1473.437063
- `PASS` full-corpus ledger headers-only size MiB: actual=2.025453 expected=2.025453
- `PASS` full-corpus ledger plus membership size MiB: actual=380.515149 expected=380.515149
- `PASS` full-corpus verification passed: actual=True expected=True
