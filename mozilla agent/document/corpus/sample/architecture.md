# Architecture Decision Record: Payment Retry Logic

**Status:** Accepted
**Date:** 2024-09-15
**Author:** Engineering Team

## Context

Our payment processing service handles approximately 50,000 transactions per day. Roughly 3-5% of initial payment attempts fail due to transient errors from downstream payment providers (network timeouts, rate limits, temporary provider outages).

We need a retry strategy that maximizes successful payment completion without overwhelming downstream providers or creating duplicate charges.

## Decision

We will implement exponential backoff with jitter for all retryable payment failures.

### Retry Configuration

- **Max retries:** 5 attempts total (1 initial + 4 retries)
- **Base delay:** 2 seconds
- **Max delay:** 120 seconds (cap)
- **Jitter:** Full jitter — random value between 0 and the calculated delay
- **Backoff formula:** `min(max_delay, base_delay * 2^attempt) * random(0, 1)`

### Retryable vs Non-Retryable Errors

**Retryable (will retry):**
- HTTP 429 (rate limited)
- HTTP 500, 502, 503, 504 (server errors)
- Network timeouts
- Connection refused

**Non-retryable (will NOT retry):**
- HTTP 400 (bad request — our payload is wrong)
- HTTP 401, 403 (auth errors)
- HTTP 409 (duplicate/conflict)
- HTTP 422 (validation failed — card declined, insufficient funds)
- Any response with an explicit "do not retry" flag from the provider

### Idempotency

Every payment request includes an idempotency key (UUID v4, generated at the first attempt and reused across retries). This prevents duplicate charges if a request succeeds but the response is lost.

The idempotency key format is: `pay_{merchant_id}_{order_id}_{timestamp_ms}`

## Consequences

- Failed payments that are retryable will be retried up to 4 additional times with increasing delays.
- The jitter prevents thundering herd problems when a provider recovers from an outage.
- Non-retryable failures surface immediately to the user without delay.
- The 120-second cap means the worst-case total retry window is approximately 4 minutes.
- We must monitor retry rates per provider to detect sustained outages early.

## Monitoring

- Alert if retry rate exceeds 10% of total requests over a 5-minute window.
- Dashboard tracks: retry count by attempt number, provider error rates, idempotency key collision rate (should be ~0).
