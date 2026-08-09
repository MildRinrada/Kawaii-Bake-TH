# 0004 — Infrastructure Package for External Services

- **Status:** Accepted
- **Date:** 2026-08-06

## Context

External concerns (cache, object storage, email delivery, task queue, search,
logging) tend to leak vendor-specific code into business logic, making later
migrations (e.g. local disk → S3, SMTP → provider API) expensive.

## Decision

A dedicated `infrastructure/` package wraps every external service behind a
small base interface with concrete adapters (e.g. `storage/base.py` +
`storage/s3_storage.py`). Services depend on the interface, never the vendor.

## Consequences

- Vendor swaps are adapter swaps; business logic is untouched.
- Test doubles are trivial (in-memory cache, console email).
- Slight indirection cost — acceptable for a multi-year codebase.
