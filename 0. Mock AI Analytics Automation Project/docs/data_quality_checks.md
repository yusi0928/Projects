# Data Quality Checks

Quality checks are executed by `scripts/build_sqlite_stack.py`.

Checks include:

- Primary key uniqueness for raw source tables
- Accepted values for contact status
- CSAT scores between 1 and 5
- Non-negative handling time and compensation values
- Mart uniqueness at `week_start + country_code + contact_reason_id`
- Rate metrics within expected bounds
- AI-safe mart excludes direct customer and agent identifiers

The AI/reporting layer should not run if these checks fail.
