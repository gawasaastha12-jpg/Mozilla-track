# Payment Service API Specification

**Base URL:** `https://api.internal.example.com/v2/payments`
**Authentication:** Bearer token (JWT) in the `Authorization` header.
**Rate Limit:** 100 requests/second per merchant. Returns HTTP 429 when exceeded.

## Endpoints

### POST /charge

Create a new payment charge.

**Request Body:**

```json
{
  "merchant_id": "merch_abc123",
  "order_id": "ord_def456",
  "amount_cents": 4999,
  "currency": "USD",
  "payment_method": {
    "type": "card",
    "token": "tok_visa_4242"
  },
  "metadata": {
    "customer_email": "user@example.com",
    "order_source": "web"
  }
}
```

**Response (201 Created):**

```json
{
  "charge_id": "chg_789xyz",
  "status": "succeeded",
  "amount_cents": 4999,
  "currency": "USD",
  "provider": "stripe",
  "idempotency_key": "pay_merch_abc123_ord_def456_1694800000000",
  "created_at": "2024-09-15T14:30:00Z"
}
```

**Error Response (422 Unprocessable):**

```json
{
  "error": {
    "code": "card_declined",
    "message": "The card was declined due to insufficient funds.",
    "retryable": false
  }
}
```

### GET /charge/{charge_id}

Retrieve a charge by ID.

**Response (200 OK):** Same shape as POST response, with additional fields:

```json
{
  "charge_id": "chg_789xyz",
  "status": "succeeded",
  "amount_cents": 4999,
  "currency": "USD",
  "provider": "stripe",
  "retry_count": 0,
  "idempotency_key": "pay_merch_abc123_ord_def456_1694800000000",
  "created_at": "2024-09-15T14:30:00Z",
  "updated_at": "2024-09-15T14:30:01Z"
}
```

### POST /refund

Refund a previous charge (full or partial).

**Request Body:**

```json
{
  "charge_id": "chg_789xyz",
  "amount_cents": 4999,
  "reason": "customer_request"
}
```

Omit `amount_cents` for a full refund. Valid reasons: `customer_request`, `duplicate`, `fraudulent`.

**Response (201 Created):**

```json
{
  "refund_id": "ref_abc123",
  "charge_id": "chg_789xyz",
  "amount_cents": 4999,
  "status": "pending",
  "reason": "customer_request",
  "created_at": "2024-09-15T15:00:00Z"
}
```

### GET /merchants/{merchant_id}/charges

List charges for a merchant. Supports pagination.

**Query Parameters:**
- `limit` (int, default 20, max 100)
- `offset` (int, default 0)
- `status` (string, optional): Filter by `succeeded`, `failed`, `pending`
- `created_after` (ISO 8601, optional)
- `created_before` (ISO 8601, optional)

## Webhooks

We send webhooks to the URL configured in the merchant dashboard.

**Events:**
- `charge.succeeded` — payment completed
- `charge.failed` — payment failed (non-retryable)
- `charge.refunded` — refund processed
- `charge.disputed` — chargeback initiated

**Payload:**

```json
{
  "event": "charge.succeeded",
  "data": { /* charge object */ },
  "timestamp": "2024-09-15T14:30:01Z",
  "webhook_id": "wh_unique_id"
}
```

Webhooks retry on failure with exponential backoff (same policy as our payment retries). After 5 failed deliveries, the webhook is marked as dead and an alert is sent to the merchant's configured email.

## Status Codes Summary

| Code | Meaning | Retryable? |
|------|---------|------------|
| 200  | Success | N/A |
| 201  | Created | N/A |
| 400  | Bad request | No |
| 401  | Unauthorized | No |
| 404  | Not found | No |
| 409  | Conflict (duplicate) | No |
| 422  | Validation failed | No |
| 429  | Rate limited | Yes |
| 500  | Internal error | Yes |
| 502  | Bad gateway | Yes |
| 503  | Service unavailable | Yes |
