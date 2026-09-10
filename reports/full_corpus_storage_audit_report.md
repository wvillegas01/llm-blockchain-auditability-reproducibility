# Full-corpus storage audit for reviewer revision

Date: 2026-08-28

## Scope

This revision run regenerates HMAC-SHA-256 hash-only audit records for the full normalized corpus and constructs a streaming lightweight ledger with membership evidence.

## Key results

- Interaction audit records: 3,932,629
- Comparison audit records: 39,258
- Total audit records: 3,971,887
- Audit-record footprint: 1473.437063 MiB
- Ledger block headers: 2.025453 MiB
- Ledger + membership: 380.515149 MiB
- Off-chain normalized repository: 11899.551530 MiB
- Audit-record reduction vs off-chain: 87.617709%
- Ledger+membership reduction vs off-chain: 96.802273%
- Verification passed: True
- Verification throughput: 64566.12 records/s

## Storage table

| Category | Artifact | Rows | Size MiB |
|---|---|---:|---:|
| offchain | normalized_interactions | 3932629 | 11858.375467 |
| offchain | normalized_comparisons | 39258 | 41.176063 |
| audit_records | audit_records_full_hmac | 3932629 | 1454.885699 |
| audit_records | comparison_audit_records_full_hmac | 39258 | 18.551364 |
| ledger | ledger_blocks_full |  | 2.025453 |
| ledger | ledger_record_membership_full | 3971887 | 378.489697 |
