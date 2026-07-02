# Privacy Controls

This repository uses synthetic data only.

## Implemented Controls

- No customer names, emails, phone numbers, addresses, or free-text support messages.
- Customer and agent identifiers are hashed-looking synthetic IDs.
- The AI-safe layer is aggregated to weekly country/contact-reason grain.
- The mart does not expose customer-level or agent-level identifiers.

## Real Enterprise Controls

- Keep raw contact-level data in a restricted access layer.
- Redact or exclude free-text fields before AI usage.
- Tokenize customer and agent identifiers.
- Allow AI to consume only approved marts, metric definitions, data quality status, and analyst validation notes.
- Log AI prompt inputs and outputs for auditability.
