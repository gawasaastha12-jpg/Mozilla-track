# Runbook: Payment Processing Incidents

## On-Call Rotation

Payment processing on-call rotates weekly. Check #payments-oncall in Slack for the current on-call engineer. Escalation path: on-call → team lead → VP Engineering.

## Common Scenarios

### Scenario 1: High Retry Rate Alert

**Trigger:** Retry rate exceeds 10% over 5 minutes.

**Steps:**
1. Check the provider status dashboard at `internal.example.com/dashboards/payments`
2. Identify which provider is failing — look at error rates grouped by `provider_id`
3. If a single provider is down:
   - Enable the circuit breaker for that provider: `./scripts/circuit-breaker.sh enable <provider_id>`
   - This routes traffic to the fallback provider automatically
   - Notify #payments-incidents with provider name and estimated impact
4. If multiple providers are failing, check our own infrastructure (load balancer, database connections)
5. Once the provider recovers, disable the circuit breaker: `./scripts/circuit-breaker.sh disable <provider_id>`

**Resolution time target:** Acknowledge within 5 minutes, mitigate within 15 minutes.

### Scenario 2: Duplicate Charge Report

**Trigger:** Customer reports being charged twice for the same order.

**Steps:**
1. Look up the order in the admin panel: `internal.example.com/admin/orders/<order_id>`
2. Check the idempotency key — both charges should have the same key if our retry logic created them
3. If keys differ: this is NOT a retry issue. Escalate to the frontend team (likely a double-submit bug).
4. If keys match: the provider failed to honor idempotency. File a bug with the provider and refund the duplicate.
5. Log the incident in the payments incident tracker for monthly review.

### Scenario 3: Timeout Spike

**Trigger:** p99 latency exceeds 10 seconds.

**Steps:**
1. Check if a specific provider is slow: `internal.example.com/dashboards/latency-by-provider`
2. If provider latency is high, their infrastructure is likely under load. Our retry logic will handle transient cases.
3. If OUR latency is high (not provider-side), check:
   - Database connection pool saturation: `pg_stat_activity` count
   - Redis queue depth for async payment jobs
   - CPU/memory on payment worker pods
4. Consider scaling up workers: `kubectl scale deployment payment-workers --replicas=8`

## Circuit Breaker Configuration

The circuit breaker trips after 5 consecutive failures to a single provider within 30 seconds. When tripped:
- All new requests to that provider are routed to the fallback
- The breaker attempts a single probe request every 60 seconds
- After 3 consecutive successful probes, the breaker resets

Configuration lives in `config/circuit-breaker.yaml`. Do NOT change thresholds without team lead approval.

## Contacts

- **Stripe support:** enterprise-support@stripe.com (response SLA: 1 hour)
- **Internal payments team lead:** @jordan in Slack
- **VP Engineering (escalation):** @sam in Slack
