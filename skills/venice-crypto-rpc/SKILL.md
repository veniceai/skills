---
name: venice-crypto-rpc
description: Use Venice as a pay-per-call JSON-RPC proxy to 27 EVM, Starknet, and Solana networks. Covers the public GET /crypto/rpc/networks, POST /crypto/rpc/{network}, chain families and their explicit per-family method allowlists, the 1×/2×/4× method-tier pricing model (~$7e-7 per credit), the per-minute rate limit and per-user request serialization, idempotency keys for safe retries, single vs batch (≤100) requests, and the unsupported stateful/WebSocket methods (eth_subscribe, eth_newFilter, *Subscribe, etc.).
---

# Venice Crypto RPC (JSON-RPC proxy)

Venice exposes a **multi-chain JSON-RPC proxy** billed per call. Same request shape as Alchemy / Infura — change the base URL and pay per credit from your Venice balance (DIEM → earned credits → bundled credits → USD) or an x402 wallet.

| Endpoint | Auth | Notes |
|---|---|---|
| `GET /crypto/rpc/networks` | **None** (public) | Returns `{ "networks": [...] }`, sorted alphabetically. |
| `POST /crypto/rpc/{network}` | Bearer API key (`INFERENCE` or `ADMIN`) or `SIGN-IN-WITH-X` (x402 wallet) | Forward a JSON-RPC 2.0 request (single or batch). |

## Supported networks

```bash
curl https://api.venice.ai/api/v1/crypto/rpc/networks
```

It currently returns 27 slugs (always verify — the catalog grows):

```
arbitrum-mainnet    arbitrum-sepolia
avalanche-mainnet   avalanche-fuji
base-mainnet        base-sepolia
blast-mainnet       blast-sepolia
bsc-mainnet         bsc-testnet
ethereum-mainnet    ethereum-sepolia    ethereum-holesky
linea-mainnet       linea-sepolia
optimism-mainnet    optimism-sepolia
polygon-mainnet     polygon-amoy
robinhood-mainnet   robinhood-testnet
solana-mainnet      solana-devnet
starknet-mainnet    starknet-sepolia
zksync-mainnet      zksync-sepolia
```

Use the slug as `{network}` in the proxy path. An unknown slug is a `400`. The spec's example list for `/networks` omits `blast-mainnet` / `blast-sepolia`, but the live endpoint and proxy include them — trust `GET /crypto/rpc/networks`, and don't hardcode a client-side allowlist.

### Chain families

Each network speaks exactly one method family, and the allowlist is enforced per family. Sending an EVM method to a Solana network (or the reverse) is a `400`, not a pass-through.

| Family | Networks |
|---|---|
| `evm` | Everything except Starknet and Solana, including Robinhood Chain (an Arbitrum Orbit L2). |
| `starknet` | `starknet-mainnet`, `starknet-sepolia` |
| `solana` | `solana-mainnet`, `solana-devnet` |

The allowlists are **explicit method names**, not prefixes: a method in a supported namespace that isn't on the list (e.g. an unlisted `debug_*` or `trace_*` method) is rejected. The EVM list is shared by every EVM network, so a chain-specific method (`zks_*`, `linea_*`, `bor_*`) passes Venice's check on any EVM chain but only works upstream on its own chain.

## Send a JSON-RPC request

### Single call

```bash
curl -X POST https://api.venice.ai/api/v1/crypto/rpc/ethereum-mainnet \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_chainId","params":[],"id":1}'
```

```json
{ "jsonrpc": "2.0", "id": 1, "result": "0x1" }
```

Each request object must have a string `method`; otherwise `400`.

### Batch (up to 100 calls)

```bash
curl -X POST https://api.venice.ai/api/v1/crypto/rpc/base-mainnet \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '[
    {"jsonrpc":"2.0","method":"eth_chainId","params":[],"id":1},
    {"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":2}
  ]'
```

- An empty array or more than 100 items ⇒ `400`.
- A single unsupported method in a batch ⇒ the **entire batch** fails with `400`, and the message lists every offending method. (A WebSocket-only method fails the batch immediately with its own message naming just that method.)
- Give every item a unique `id`: billing pairs response items to requests by `id`.

### Drop-in with `viem`

```ts
import { createPublicClient, http } from 'viem'
import { mainnet } from 'viem/chains'

const client = createPublicClient({
  chain: mainnet,
  transport: http('https://api.venice.ai/api/v1/crypto/rpc/ethereum-mainnet', {
    fetchOptions: { headers: { Authorization: `Bearer ${process.env.VENICE_API_KEY}` } },
  }),
})
```

## Pricing

Credits per call = `baseCredits[chain] × methodTier`, at `$0.0000007` (7e-7) per credit.

| Base credits | Chains |
|---|---|
| `20` | Ethereum, Base, Optimism, Arbitrum, Polygon, Linea, Avalanche, BSC, Blast, Robinhood, Starknet (mainnets and testnets). |
| `30` | zkSync Era, Solana. |

| Tier | Multiplier | Methods |
|---|---|---|
| **Standard** | `1×` | EVM core (`eth_call`, `eth_getBalance`, `eth_blockNumber`, `eth_chainId`, `eth_getLogs`, `eth_estimateGas`, `eth_feeHistory`, `eth_getBlockReceipts`, `eth_getProof`, `eth_simulateV1`, `eth_sendRawTransaction`, …), `net_version` / `net_listening` / `net_peerCount`, `web3_clientVersion` / `web3_sha3`, ERC-4337 bundler (`eth_sendUserOperation`, `eth_estimateUserOperationGas`, `eth_getUserOperationByHash`, `eth_getUserOperationReceipt`, `eth_supportedEntryPoints`, `pimlico_getUserOperationGasPrice`, `pimlico_getUserOperationStatus`), chain extensions (`zks_*`, `linea_*`, `bor_*` — listed methods only), all listed `starknet_*` methods, and Solana methods (`getAccountInfo`, `getBalance`, `getLatestBlockhash`, `getProgramAccounts`, `sendTransaction`, `simulateTransaction`, …). |
| **Advanced** | `2×` | `trace_block`, `trace_call`, `trace_callMany`, `trace_filter`, `trace_transaction`, `trace_rawTransaction`, `debug_traceBlock`, `debug_traceBlockByHash`, `debug_traceBlockByNumber`, `debug_traceCall`, `debug_traceTransaction`, `debug_storageRangeAt`, `txpool_inspect`, `txpool_status`, `arbtrace_block` / `_call` / `_callMany` / `_filter` / `_transaction`. EVM only. |
| **Large** | `4×` | `trace_replayBlockTransactions`, `trace_replayTransaction`, `txpool_content`, `arbtrace_replayBlockTransactions`, `arbtrace_replayTransaction`, and Solana `getLargestAccounts` / `getSupply`. |

Examples:

- Standard EVM call (20 × 1 = 20 credits) = **$0.000014**
- Advanced trace on Ethereum (20 × 2) = **$0.000028**
- Large trace replay (20 × 4) = **$0.000056**
- zkSync or Solana standard call (30 × 1) = **$0.000021**
- Solana `getLargestAccounts` (30 × 4) = **$0.000084**

Error billing:

- An item that comes back with a JSON-RPC `error` (HTTP 200 — e.g. bad params, method not available on that chain) is billed a flat **5 credits** instead of its tier. In a batch, a success item whose `id` doesn't match a request is also billed 5.
- If the upstream node returns HTTP 4xx, each item is billed 5 credits. Upstream 402, 429, and 5xx are billed **0**.
- Requests Venice rejects itself (`400`, `401`, `402`, `429`) are not billed.

Before forwarding, Venice checks that the balance of your current consumption currency covers the estimated full-tier cost; otherwise `402`.

### Response headers

Set on every response relayed from the node (any status) and on idempotent replays; responses Venice generates itself (validation errors, `402`, `429`, upstream-fetch `500`) don't carry them.

| Header | Meaning |
|---|---|
| `X-Venice-RPC-Credits` | Total credits charged (sum over the batch). On a replay it repeats the original call's credits, although the replay itself is not billed. |
| `X-Venice-RPC-Cost-USD` | Dollar cost to 8 decimal places. |
| `X-Request-ID` | 32-char correlation ID — include in support tickets. |
| `Idempotent-Replayed` | `"true"` when served from the idempotency cache. |

On `2xx` the `Content-Type` is always `application/json`; upstream error bodies are sanitized before being forwarded. The spec also lists `X-Balance-Remaining` for x402 callers, but the proxy does not set it — use `GET /x402/balance/{walletAddress}`.

## Unsupported methods

These always return `400`:

- **Stateful filter methods** — `eth_newFilter`, `eth_newBlockFilter`, `eth_newPendingTransactionFilter`, `eth_getFilterChanges`, `eth_getFilterLogs`, `eth_uninstallFilter`. Filter state is pinned to one backend and a load-balanced HTTP proxy can't keep it. Use `eth_getLogs` instead.
- **WebSocket-only methods** — EVM `eth_subscribe` / `eth_unsubscribe` and Solana `*Subscribe` / `*Unsubscribe` (account, block, logs, program, root, signature, slot, slotsUpdates, vote). This proxy is HTTP only.
- **Wallet / miner methods** — `eth_sign`, `eth_accounts`, `eth_getWork`, `eth_submitWork`, `eth_mining`, `eth_hashrate`.
- **Solana add-ons and legacy aliases** — `getAsset*` (DAS) and deprecated `getConfirmed*`.
- **Cross-family methods** — `starknet_*` or Solana `getBalance` on an EVM chain, `eth_call` on Solana, etc.
- **Anything else not on the allowlist.** The error message names the rejected methods.

## Idempotency

Set `Idempotency-Key` to a string matching `[A-Za-z0-9_-]{1,255}` for safe retries:

```bash
curl -X POST https://api.venice.ai/api/v1/crypto/rpc/ethereum-mainnet \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Idempotency-Key: send-tx-2026-04-21-nonce-42" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_sendRawTransaction","params":["0x..."],"id":1}'
```

- The full response (status, body, credits, `X-Request-ID`) is cached for **24 hours** keyed on `(user, idempotency-key)`.
- A replay with the same body returns the cached response with `Idempotent-Replayed: true` and is **not billed again**. Replays still count toward the per-minute rate limit.
- Same key + **different body** ⇒ `400`.
- A key that doesn't match the pattern is **silently ignored** (the request runs without idempotency) — validate keys client-side.
- Caching is best-effort and happens after the response is sent; a replay that arrives before the original finishes is not deduplicated.

Use this for state-mutating methods (`eth_sendRawTransaction`, `eth_sendUserOperation`, Solana `sendTransaction`) so a network retry doesn't double-broadcast.

## Rate limits and concurrency

- **100 requests per minute** per user. Every request counts, including ones later rejected with `400` and idempotent replays.
- Over the cap ⇒ `429` with `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `X-RateLimit-Reset` (Unix seconds). The breach also shows in `GET /api_keys/rate_limits/log` (ADMIN key only) as `modelId: "endpoint:api/v1/crypto/rpc"`.
- A batch counts as **one** request, so batching is the way to raise throughput.
- Requests are **processed one at a time per user**. A concurrent request waits briefly (~0.5 s) and otherwise gets `429` `"Another request for this user is in flight"`. Retry with jitter, or batch instead of fanning out in parallel.
- There is no daily credit cap. (The spec text still mentions a 10,000,000-credits/24h cap; it no longer applies.)
- Upstream calls time out after 30 s.

## Errors

| Status | Typical cause |
|---|---|
| `400` | Unknown network slug, empty body or batch, batch > 100, item without a string `method`, unsupported / WebSocket / filter / cross-family method, idempotency-key reuse with a different body. |
| `401` | Invalid Bearer key or invalid `SIGN-IN-WITH-X`. |
| `402` | No credentials at all (x402 auth challenge with `authOptions`); balance below the estimated cost; per-key spend limit reached; or an x402 wallet under $0.10 (body carries top-up instructions — see [`venice-x402`](../venice-x402/SKILL.md)). |
| `429` | Per-minute cap, another request from the same user still in flight, the generic API error budget, or x402's 5-concurrent-request limit. |
| `500` | Upstream fetch failed / timed out, or the service is misconfigured. Safe to retry with the same `Idempotency-Key`. |
| other | Non-2xx statuses from the upstream node are passed through (sanitized). |

## Patterns

- **Multi-chain dashboards** — One API key covers every network. No per-chain keys to rotate.
- **High-throughput indexing** — Batch up to 100 calls per request; each item is billed individually, but it's one request against the rate limit and the one-at-a-time rule.
- **Wallet-based (x402) RPC** — Top up USDC on Base or Solana, then send `SIGN-IN-WITH-X`. A `402` means low credit and carries top-up instructions.
- **Cost tracking** — Log `X-Venice-RPC-Credits` and `X-Venice-RPC-Cost-USD` per request (skip responses with `Idempotent-Replayed: true`, which weren't billed); aggregate by method to see where credits go. Ledger entries use the SKU `crypto-rpc-<network>`.
- **Safe transaction submission** — Always send an `Idempotency-Key` with `eth_sendRawTransaction` so client retries within 24 hours replay instead of rebroadcasting.
