# DEVELOPMENT_RULES.md — PriceRadar India

> These rules govern how this codebase is built, by humans and by AI coding agents alike.
> They are enforced procedurally via `.cursor/rules/` and must not be bypassed for convenience.

## 1. Phase-by-Phase Development

1. Work happens **phase by phase**, as defined in `ROADMAP.md`.
2. **Never implement a future phase** unless explicitly requested by the project owner, even
   if it seems efficient to "get ahead."
3. Each phase must leave the system in a working, tested state before the next phase begins.
4. If a task appears to require work from a later phase (e.g. a database model while working
   on Phase 0 docs), stop and flag it rather than implementing it silently.

## 2. Inspect Before You Modify

1. Always inspect the existing repository state before creating or modifying files.
2. Never assume a file, module, or directory doesn't exist — check first.
3. Never rewrite a working module "for style" or "for cleanliness" unless the task explicitly
   calls for a refactor. Prefer minimal, targeted changes.
4. When extending existing functionality, follow the existing patterns and conventions in the
   codebase rather than introducing a competing pattern.

## 3. Retailer & Data Integrity Rules

1. Never fabricate, guess, or "fill in" retailer prices, availability, or product data. All
   data must trace back to a legitimate source (official API, affiliate/partner feed, or other
   permitted structured source).
2. Never write code intended to bypass CAPTCHA, authentication, anti-bot protection, access
   controls, rate limits, `robots.txt` restrictions, or retailer terms of service.
3. Every retailer integration must be isolated behind the common retailer adapter interface
   (see `RETAILER_ARCHITECTURE.md`). Core comparison, matching, and pricing logic must never
   contain retailer-specific branching (e.g. `if retailer == "X"`).
4. Every Price Observation must carry: retailer, seller, source URL, observation timestamp,
   displayed price, MRP (where available), effective price (where calculable), availability,
   source type, and a data freshness/confidence indicator.
5. Observed, calculated, and predicted values must never be merged or presented ambiguously.
   Predictions are always labeled as predictions.

## 4. Secrets & Configuration

1. Never hardcode secrets, API keys, credentials, or connection strings in source code.
2. All configuration must be sourced from environment variables in local/dev, and from Azure
   Key Vault (via managed identity) in deployed environments.
3. `.env` files are never committed. `.env.example` documents required variables with
   placeholder values only.

## 5. Engineering Quality Bar

1. Use modular architecture with clear boundaries between layers (see
   `PROJECT_ARCHITECTURE.md`).
2. Use strong typing: TypeScript on the frontend, Python type hints + Pydantic on the backend.
3. Validate all external input (API requests, retailer feed payloads) at the boundary.
4. Write unit tests for business logic and integration tests for cross-component behavior as
   each phase introduces real logic.
5. Use structured logging (JSON), not ad-hoc `print`/`console.log` debugging left in place.
6. Expose health checks for every deployable service.
7. Network calls (retailer APIs/feeds, internal services) must use explicit timeouts and
   retries with backoff — never unbounded blocking calls.
8. Track metrics for anything operationally important (collection success rate, data
   freshness, API latency, job failures).
9. Document new modules with a short README or module-level docstring explaining purpose and
   boundaries.

## 6. Testing Discipline

1. After implementing any change, run the relevant tests for the affected area.
2. A task is not complete if it introduces failing tests, and it is preferable to deliver a
   change with clearly reported failing/missing tests than to skip verification silently.
3. New business logic must be accompanied by new or updated tests in the same change.

## 7. Reporting

At the end of every implementation task, report:

1. **Files created.**
2. **Files modified.**
3. **Tests executed** (and their results).
4. **Remaining issues** or known gaps.

## 8. Stopping Points

1. When a phase's defined scope is complete, stop and wait for the next instruction rather
   than continuing into unrequested work.
2. If a request conflicts with these rules (e.g. asks to bypass a retailer's anti-bot system,
   or to fabricate data), decline that specific part and explain why, while still completing
   any parts of the request that are compliant.
