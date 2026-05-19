---
name: relayshield-security
description: Identity threat intelligence and security scanning via RelayShield. Use this skill when an agent needs to check email breach exposure, detect SIM swap attacks, scan for typosquat/phishing domains, audit OAuth app risk, assess EVM wallet safety, or analyze URLs and files for malware. Covers POST /breach, /sim-swap, /domain, /oauth-watchlist, /scan-wallet, /scan-url, /scan-file, and GET /result/{id}. Supports pay-as-you-go via x402 USDC on Base or subscription via RapidAPI key.
---

# RelayShield Security Intelligence

RelayShield provides real-time identity threat intelligence via a REST API. Use it to verify credential integrity, detect account takeover vectors, and screen on-chain and web threats before acting on user input or executing transactions. Eight endpoints cover the full identity attack surface. Payment is either pay-as-you-go with USDC on Base (x402) or subscription via RapidAPI.

- **API base:** `https://xhh3tfrhng.execute-api.us-east-1.amazonaws.com/prod`
- **x402 PAYG path:** `/v1/payg/<endpoint>`
- **RapidAPI subscription path:** `/v1/<endpoint>`
- **Free tier:** [rapidapi.com/relayshielduser/api/relayshield-security-intelligence](https://rapidapi.com/relayshielduser/api/relayshield-security-intelligence)
- **Docs / MCP:** [relayshield.net](https://relayshield.net)

## Endpoints

| Method | Path | What it does | Cost (x402) |
|---|---|---|---|
| `POST` | `/breach` | Email breach lookup — HIBP 13B+ records | $0.10 USDC |
| `POST` | `/sim-swap` | SIM swap / eSIM detection via live carrier data | $0.25 USDC |
| `POST` | `/domain` | Typosquat & lookalike domain scan with DNS + CT enrichment | $0.50 USDC |
| `POST` | `/oauth-watchlist` | Breached OAuth-connected SaaS apps for an email | $0.15 USDC |
| `POST` | `/scan-wallet` | EVM wallet risk via GoPlus — blacklists, phishing, contract flags | $0.10 USDC |
| `POST` | `/scan-url` | Malware/phishing URL scan across 70+ engines (async) | $0.05 USDC |
| `POST` | `/scan-file` | Binary malware scan across 70+ AV engines (async) | $0.10 USDC |
| `GET` | `/result/{analysis_id}` | Poll async scan result (scan-url / scan-file) | Free |

## Authentication

### Option A — x402 PAYG (USDC on Base, no account required)

Use the `/v1/payg/` path prefix and include a signed x402 payment proof header:

```bash
curl -X POST \
  https://xhh3tfrhng.execute-api.us-east-1.amazonaws.com/prod/v1/payg/breach \
  -H "Content-Type: application/json" \
  -H "X-PAYMENT: $RELAYSHIELD_X_PAYMENT" \
  -d '{"email": "user@example.com"}'
```

x402 on Base (chain 8453) — same protocol as Venice's own wallet credits. Use `npm install x402` to generate the `X-PAYMENT` header from a funded Base wallet.

### Option B — RapidAPI subscription key

Use the `/v1/` path prefix and include your RapidAPI key:

```bash
curl -X POST \
  https://xhh3tfrhng.execute-api.us-east-1.amazonaws.com/prod/v1/breach \
  -H "Content-Type: application/json" \
  -H "x-api-key: $RELAYSHIELD_API_KEY" \
  -d '{"email": "user@example.com"}'
```

## Quick start

### Check email breach exposure

```bash
curl -X POST \
  https://xhh3tfrhng.execute-api.us-east-1.amazonaws.com/prod/v1/payg/breach \
  -H "Content-Type: application/json" \
  -H "X-PAYMENT: $RELAYSHIELD_X_PAYMENT" \
  -d '{"email": "user@example.com"}'
```

```json
{
  "breached": true,
  "breach_count": 4,
  "breaches": [
    { "name": "ExampleBreach", "date": "2023-06-01", "data_classes": ["Passwords", "Email addresses"] }
  ]
}
```

### Detect SIM swap

```bash
curl -X POST \
  https://xhh3tfrhng.execute-api.us-east-1.amazonaws.com/prod/v1/payg/sim-swap \
  -H "Content-Type: application/json" \
  -H "X-PAYMENT: $RELAYSHIELD_X_PAYMENT" \
  -d '{"phone": "+14155551234"}'
```

```json
{
  "swapped": true,
  "swapped_at": "2026-05-18T14:23:00Z",
  "carrier": "T-Mobile"
}
```

### Scan domain for lookalikes

```bash
curl -X POST \
  https://xhh3tfrhng.execute-api.us-east-1.amazonaws.com/prod/v1/payg/domain \
  -H "Content-Type: application/json" \
  -H "X-PAYMENT: $RELAYSHIELD_X_PAYMENT" \
  -d '{"domain": "acme.com"}'
```

```json
{
  "lookalikes": [
    { "domain": "acrne.com", "resolved": true, "has_cert": true },
    { "domain": "acme-login.com", "resolved": true, "has_cert": false }
  ],
  "total": 2
}
```

### Check EVM wallet risk

```bash
curl -X POST \
  https://xhh3tfrhng.execute-api.us-east-1.amazonaws.com/prod/v1/payg/scan-wallet \
  -H "Content-Type: application/json" \
  -H "X-PAYMENT: $RELAYSHIELD_X_PAYMENT" \
  -d '{"address": "0xAbC...123", "chain_id": "8453"}'
```

```json
{
  "risk_level": "LOW",
  "risk_flags": []
}
```

### Scan URL for malware (async)

```bash
# Step 1 — submit
curl -X POST \
  https://xhh3tfrhng.execute-api.us-east-1.amazonaws.com/prod/v1/payg/scan-url \
  -H "Content-Type: application/json" \
  -H "X-PAYMENT: $RELAYSHIELD_X_PAYMENT" \
  -d '{"url": "https://suspicious-site.example.com"}'
# Returns: { "analysis_id": "abc123" }

# Step 2 — poll every 5 seconds until status == "completed"
curl https://xhh3tfrhng.execute-api.us-east-1.amazonaws.com/prod/v1/payg/result/abc123 \
  -H "X-PAYMENT: $RELAYSHIELD_X_PAYMENT"
```

```json
{
  "status": "completed",
  "verdict": "malicious",
  "malicious": 12,
  "suspicious": 3,
  "clean": 58
}
```

## Parameters

### `/breach`
| Field | Type | Required | Notes |
|---|---|---|---|
| `email` | string | ✅ | Email address to check |

### `/sim-swap`
| Field | Type | Required | Notes |
|---|---|---|---|
| `phone` | string | ✅ | E.164 format — e.g. `+14155551234` |

### `/domain`
| Field | Type | Required | Notes |
|---|---|---|---|
| `domain` | string | ✅ | Root domain — e.g. `acme.com` |

### `/oauth-watchlist`
| Field | Type | Required | Notes |
|---|---|---|---|
| `email` | string | ✅ | Email whose OAuth-linked apps to check |

### `/scan-wallet`
| Field | Type | Required | Notes |
|---|---|---|---|
| `address` | string | ✅ | EVM address (0x + 40 hex chars) |
| `chain_id` | string | ❌ | Default `"1"` (Ethereum). Also: `"8453"` (Base), `"137"` (Polygon), `"42161"` (Arbitrum), `"56"` (BSC) |

### `/scan-url`
| Field | Type | Required | Notes |
|---|---|---|---|
| `url` | string | ✅ | Must start with `http://` or `https://` |

### `/scan-file`
| Field | Type | Required | Notes |
|---|---|---|---|
| `file_url` | string | ✅ | Publicly accessible download URL |
| `filename` | string | ❌ | Hint for AV engines — e.g. `invoice.pdf` |

## Errors

| Status | Cause | Fix |
|---|---|---|
| `402` | No valid payment header or API key | Set `X-PAYMENT` (x402) or `x-api-key` (RapidAPI) |
| `400` | Missing or invalid required field | Validate input format — phone must be E.164, address must be 0x-prefixed |
| `429` | Rate limit exceeded | Back off with jitter; upgrade plan on RapidAPI |
| `500` | Upstream provider error | Retry once; some checks depend on third-party carrier/DNS APIs |

## Gotchas

- **Async scans** (`scan-url`, `scan-file`) return an `analysis_id` immediately. Poll `/result/{analysis_id}` every 5 seconds — scans typically complete in 15–60 seconds. A `timeout` verdict means the engines didn't finish; retry the original scan.
- **x402 path vs subscription path** — PAYG uses `/v1/payg/` prefix; RapidAPI subscription uses `/v1/` prefix. Using the wrong prefix returns `403`.
- **SIM swap requires live carrier lookup** — result latency is 3–8 seconds. Don't set timeouts below 15 seconds.
- **`scan-wallet` chain_id** — pass as a string (`"8453"`), not an integer. Base (8453) is supported for wallet risk but token approval enumeration requires an EVM indexer — this endpoint returns risk flags only.
- **OAuth watchlist** checks Slack, GitHub, Notion, Zapier, Vercel, HubSpot, and AI tools linked to the email via known breach datasets. A breached OAuth app can expose Google/Microsoft account access without touching the primary password.
- **Free tier** available on RapidAPI — limited quota, no credit card required. Good for development and testing.
