# Data Quality Results

Generated from `scripts/build_sqlite_stack.py`.

Passed 11/11 checks.

| Check | Status |
| --- | --- |
| raw_orders primary key uniqueness | PASS |
| raw_contacts primary key uniqueness | PASS |
| raw_csat_surveys primary key uniqueness | PASS |
| raw_compensation primary key uniqueness | PASS |
| valid contact status values | PASS |
| valid CSAT score range | PASS |
| non-negative handling time | PASS |
| non-negative compensation amounts | PASS |
| mart grain uniqueness | PASS |
| rate metrics within bounds | PASS |
| AI-safe mart has no direct customer or agent IDs | PASS |
