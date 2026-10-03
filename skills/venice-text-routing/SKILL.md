---
name: venice-text-routing
description: Route a prompt to the right Venice text model based on privacy tier (anonymized / private / TEE / E2EE), modality (vision / audio / video input), capability (reasoning, reasoning effort, code, function calling, X search, large context, structured output), uncensored needs, and cost. Use when a local agent (Claude Code, Hermes, NanoClaw, Codex CLI, etc.) needs to decide whether to handle a prompt locally or escalate to Venice, and if escalating, which Venice text model to call. Sits one level above venice-models (model discovery) and before venice-chat (the call surface).
---

# Venice Text-Model Routing

This skill encodes the *decision logic* for "which Venice text model do I call?" — the routing layer that sits above [`venice-chat`](../venice-chat/SKILL.md) (the call surface) and consumes [`venice-models`](../venice-models/SKILL.md) (the discovery API).

Primary use case: a **local agent** receives a prompt, decides whether the local model can handle it, and — if not — picks the cheapest Venice model that satisfies the privacy / modality / capability requirements.

## Snapshot freshness

> Before applying the matrix below, read [`snapshots/text-routing.json`](snapshots/text-routing.json). If the file is missing, **or `snapshot_date` is older than 30 days**, run `python scripts/refresh_routing.py` to regenerate it from `GET /models?type=text` + `GET /models/traits?type=text`. Otherwise trust the cached file — do **not** hit `/models` on every routing decision.

`refresh_routing.py` rewrites both [`snapshots/text-routing.json`](snapshots/text-routing.json) and [`routing-matrix.md`](routing-matrix.md). Both endpoints are public, so no key is needed; `VENICE_API_KEY` / `--api-key` is optional and tailors the result to that key (a `modelPrivacy`-restricted key sees a filtered catalog). Run it once on first install, then ~monthly (CI nightly is also fine).

In the snapshot, each model's `privacy` label is `e2ee` when `supportsE2EE` is true, `tee` when only `supportsTeeAttestation` is true, and otherwise the model's own `private` / `anonymized` value (every TEE/E2EE model is `private` in `/models`, so treat `tee` and `e2ee` as private too); `tier` is bucketed by **input** price only; `beta_access` mirrors `model_spec.beta` (only listed to beta-access keys, so it is always `false` in the shipped keyless snapshot) and `beta_status` mirrors `model_spec.betaModel` (callable, but may change or disappear).

Per model the snapshot carries only: the 13 capability flags shown in the matrix, `max_images`, `available_context_tokens`, `max_completion_tokens`, input/output price per 1M, `beta_access`, `beta_status`, `offline`, `region_restrictions` and `deprecation_date`. Filters that need anything else (`uncensored`, `supportsLogProbs`, `reasoningEffortOptions`, `maxVideos`, `cache_input` / `extended` pricing, `replacementModelId`) have to read `GET /models?type=text`.

## When to load this skill

- Picking a Venice text model from a prompt at runtime.
- Building a local-first agent that escalates to Venice for hard prompts.
- Deciding privacy tier (anonymized vs private vs TEE vs E2EE).
- Choosing between a trait shortcut (`default_reasoning`, `most_intelligent`, …) and a hand-filtered candidate.

For the chat call surface itself, see [`venice-chat`](../venice-chat/SKILL.md). For raw discovery of every model field, see [`venice-models`](../venice-models/SKILL.md).

## Privacy tier ladder

Pick the *least restrictive* tier that satisfies the request — restricting tier shrinks the candidate pool and often raises cost.

`model_spec.privacy` has only two values, `private` and `anonymized`. TEE and E2EE are capability flags on top of `private`.

| Tier | Selector (`GET /models`) | Guarantee | Use when |
|---|---|---|---|
| **Anonymized** | `privacy: "anonymized"` | Venice hides your identity from the upstream provider, but the provider may still see the prompt | Non-sensitive workloads; the only path to several closed frontier models (Claude, GPT, Gemini). |
| **Private** | `privacy: "private"` | Zero data retention, contract-enforced: content is processed for inference only and not retained | Default for user data, business logic, anything you wouldn't paste into a public chatbot. |
| **TEE** | `capabilities.supportsTeeAttestation: true` | Runs inside a hardware Trusted Execution Environment with remote attestation (`GET /api/v1/tee/attestation`) | Regulated data, verifiable/signed inference. |
| **E2EE** | `capabilities.supportsE2EE: true` | TEE + client-side encryption (ECDH secp256k1 → HKDF-SHA256 → AES-256-GCM); Venice relays ciphertext only | Strongest. Healthcare, legal, secrets. Requires the E2EE flow in [`venice-chat`](../venice-chat/SKILL.md#e2ee-end-to-end-encryption). |

Today every listed TEE model is also E2EE-capable and uses an `e2ee-*` ID (e.g. `e2ee-glm-5-3-p`, `e2ee-kimi-k3-p`, `e2ee-qwen3-8-27b`). **TEE and E2EE use the same model ID**: send E2EE headers for E2EE, omit them (or set `venice_parameters.enable_e2ee: false`) for TEE-only. Legacy `tee-*` IDs are unlisted aliases of `e2ee-*` models — don't route on the prefix; use the capability flags.

E2EE trade-offs: on E2EE requests Venice injects no web search, scraping, character, or Venice system prompt, and `file` parts return `400`; the E2EE guide also requires `stream: true` and lists function calling as unsupported (`supportsFunctionCalling` describes the model, not E2EE mode). Several E2EE models also have small limits (e.g. `e2ee-qwen-2-5-7b-p`: 32K context, 4,096 output tokens). E2EE is **not** supported on `/responses`; TEE-only is (with `enable_e2ee: false`).

API keys can carry a `modelPrivacy` restriction: `PRIVATE_TEXT` (text, embedding and decision models must be Private, TEE, or E2EE) or `PRIVATE_ONLY` (every model). Such a key's `/models` list is already filtered; a disallowed model returns `403` — filter to `privacy: "private"` for such keys.

Sources: [docs.venice.ai/overview/privacy](https://docs.venice.ai/overview/privacy), [docs.venice.ai/guides/features/tee-e2ee-models](https://docs.venice.ai/guides/features/tee-e2ee-models).

### Verifying a TEE claim

Two endpoints let you check that inference really ran inside an enclave. Both
are `GET`, **unauthenticated on purpose** (attestation evidence has to be
verifiable by any party without credentials), and rate limited to **10 requests
per minute per IP** (`429` beyond that). Neither is a path in the published
OpenAPI spec; they are live, and the `supportsTeeAttestation` capability
description in `GET /models` points at them.

| Endpoint | Query | Returns |
|---|---|---|
| `GET /api/v1/tee/attestation` | `model` (required), `nonce` (optional, exactly 64 hex chars / 32 bytes, binds the attestation to your challenge) | Attestation report, TEE provider, verification result, and the signing key/address. |
| `GET /api/v1/tee/signature` | `model` and `request_id` (required), `signing_algo` (optional `ecdsa` \| `ecdsa-p256` \| `rsa`) | The provider's signature over a specific request, plus request/response hashes. |

Both return `400` if the model exists but is not TEE-attested, and `404` if the
model ID is unknown. The attestation endpoint returns `502` (with
`verified: false`) when verification fails; both return `502` when the TEE
provider is unavailable. Chat responses from TEE models carry `X-Venice-TEE: true` and
`X-Venice-TEE-Provider`.

Verify the chain of trust in this order: fetch the attestation to get the
signing public key and hardware type, confirm the recovered signer matches the
attestation signing address, then verify the signature over the exact signed
text the signature endpoint returned. Treat the request and response hashes as
provider-reported values unless you can recompute them yourself from a
documented canonical format.

## Capability filters

Map prompt requirement → `model_spec` field (full list in the `model_spec.capabilities` section of [`venice-models`](../venice-models/SKILL.md)). Sending image / audio / video parts, `tools` / `tool_choice`, a non-`text` `response_format`, or `logprobs` to a model without the matching flag returns `400` before inference; some other features (e.g. `enable_x_search`) are silently ignored instead.

| Requirement | Filter | Notes |
|---|---|---|
| Vision (single image) | `capabilities.supportsVision` | Single-image models keep images only from the **last** image-bearing message. |
| Vision (multiple images) | `supportsVision && supportsMultipleImages` | Honor `capabilities.maxImages`. Hard cap: 10 images per message. |
| Audio input | `capabilities.supportsAudioInput` | Base64 only; URLs are not accepted. |
| Video input | `capabilities.supportsVideoInput` | `data:video/...` URLs, direct public URLs (no redirects), or YouTube links on some models. Max 3 videos per request. |
| Documents (PDF, DOCX, …) | — | Document `file` parts are extracted to text server-side, so any text model works (not on E2EE). Image files sent as `file` parts become images and need vision. |
| Reasoning | `capabilities.supportsReasoning` | To dial effort, also require `supportsReasoningEffort` and pick a value from `reasoningEffortOptions` (default: `defaultReasoningEffort`). |
| Tools / function calling | `capabilities.supportsFunctionCalling` | Required for any agent loop. |
| Code-heavy task | `capabilities.optimizedForCode` | `GET /models?type=code` returns only this subset. |
| Web search (Venice) | — | `supportsWebSearch` is `true` on every text model. Toggle with `venice_parameters.enable_web_search`. |
| X / Twitter search | `capabilities.supportsXSearch` | xAI native (Grok models). ~$0.01 per search. |
| Structured JSON output | `capabilities.supportsResponseSchema` | `response_format: {type: "json_schema", json_schema: {name, schema, strict}}`. |
| Large context | `availableContextTokens >= N` | Pair with `prompt_cache_key`; prefer models with `pricing.cache_input`. Watch `pricing.extended`, which raises prices above `context_token_threshold` input tokens. |
| Long output | `maxCompletionTokens >= N` | Requests above it are rejected on models with an enforced cap. |
| Minimal content filtering | `model_spec.uncensored: true` | Present only on models Venice classifies as uncensored; upstream providers may still filter. |
| Logprobs | `capabilities.supportsLogProbs` | Niche — eval / sampling debug. |

## Cost tiers

These buckets are this skill's own convention (the same boundaries `refresh_routing.py` uses), keyed on `model_spec.pricing.input.usd` per 1M tokens. Upper bounds are exclusive (a model at exactly $1.00 is in M), and the snapshot's `tier_boundaries_usd_per_1m_input` gives each bucket's exclusive upper bound. Pick the smallest bucket that hosts a model satisfying your filters.

| Tier | $/1M input | Use when |
|---|---|---|
| **XS** | < $0.20 | Classification, intent extraction, simple summarization. |
| **S** | $0.20 – < $1 | General chat, basic agents, light vision. |
| **M** | $1 – < $4 | Moderate reasoning, strong code, multi-image vision. |
| **L** | $4 – < $10 | Heavy reasoning, complex tool use. |
| **Frontier** | ≥ $10 | Most expensive closed models (e.g. `claude-fable-5`, `openai-gpt-6-astra`, `openai-gpt-54-pro` as of 2026-10-02). |

Output prices vary widely within a bucket (from ~1.5× to ~10× input), so tie-break on output price. Authoritative per-model pricing lives in `model_spec.pricing` (input and output rates are mirrored as `pricing_per_1m` in the snapshot) — never hard-code dollar figures from this prose.

## Routing decision tree

Walk top-down. Stop at the first rule that applies.

```
1. Local-first check
   - Prompt is ≤ ~500 tokens, no special-capability requirement,
     no privacy escalation, no tool calls expected
     → handle on the local model. Do not call Venice.

2. Privacy gate
   - User flagged "private" OR prompt contains regulated data (PHI, secrets, legal),
     OR the API key has modelPrivacy PRIVATE_TEXT / PRIVATE_ONLY:
       require model_spec.privacy === "private"   (includes every TEE/E2EE model;
       in the snapshot accept privacy "private", "tee" or "e2ee").
   - User flagged "E2EE" / "must be encrypted end to end":
       require capabilities.supportsE2EE. Use /chat/completions only.
   - User flagged "TEE" / "verifiable inference":
       require capabilities.supportsTeeAttestation.
   - Otherwise: any tier acceptable (still prefer "private" when otherwise tied).

3. Modality gate
   - Image input present  → require supportsVision (+ supportsMultipleImages if > 1).
   - Audio input present  → require supportsAudioInput.
   - Video input present  → require supportsVideoInput.

4. Capability gate
   - Tool calls expected               → require supportsFunctionCalling.
   - Code-heavy task                   → prefer optimizedForCode (or call /models?type=code).
   - Chain-of-thought / planning / hard math
                                       → require supportsReasoning;
                                         prefer supportsReasoningEffort to dial reasoning effort.
   - Structured JSON output required   → require supportsResponseSchema.
   - X/Twitter content needed          → require supportsXSearch.
   - Refusal-free / minimal filtering  → prefer model_spec.uncensored (or trait most_uncensored).

5. Context size gate
   - Estimated prompt tokens > availableContextTokens, or expected output > maxCompletionTokens
     → bump up to a model with sufficient limits. Prefer ones with cache_input pricing.

6. Frontier override
   - User asked for "best", "frontier", "most intelligent", "smartest"
     → resolve trait `most_intelligent` from the snapshot. Skip cost-min step.

7. Cost minimization
   - From surviving candidates, pick the smallest cost tier (XS → S → M → L → Frontier).
     Tie-break by lower output $/1M, then lower input $/1M.

8. Sanity filters (apply throughout)
   - Drop model_spec.beta === true (snapshot: beta_access) unless your key has
     beta access (such models are only listed to beta-access keys anyway).
     betaModel === true (snapshot: beta_status) marks callable beta-status
     models that may change or disappear; don't drop them, prefer non-beta when tied.
   - Drop model_spec.offline === true.
   - Drop candidates whose model_spec.regionRestrictions lists the caller's country (403 otherwise).
   - Prefer models without model_spec.deprecation.
```

## Trait shortcuts

When the prompt maps cleanly to a named trait, skip the matrix and resolve the trait from the snapshot's `traits` block (sourced from `GET /models/traits?type=text`). Trait names also work directly as the `model` value in a request.

| Trait | Use for | Resolves to (2026-10-02) |
|---|---|---|
| `default` | Generic chat / catch-all. | `zai-org-glm-5-2` |
| `function_calling_default` | Agent loops, tool use. | `zai-org-glm-5-2` |
| `default_reasoning` | "Think step by step" without specifying a model. | `kimi-k3` |
| `default_code` | Code generation / refactor / review. | `deepseek-v4-pro-0813` |
| `default_vision` | Vision input, no other special needs. | `qwen-3-8-27b` |
| `most_intelligent` | "Best available", frontier override. | `grok-4-7` |
| `most_uncensored` | Minimal filtering / red-team / creative writing. | `venice-uncensored-1-2` |

The mapping changes over time — always read it from the snapshot or the endpoint. Only the keys the endpoint returns exist (there is currently no `fastest` trait). Cache the resolved trait → ID map at session start (one HTTP call) and reuse.

## Local-first pattern

For a local agent driving Venice as an "escalation backend":

1. **Score the prompt cheaply** (locally):
   - Token count of prompt + expected output.
   - Modality signals (any image / audio / video parts).
   - Keyword signals: "code", "reason", "step by step", "private", "secret", "encrypt", "best", "frontier".
   - User-provided overrides (e.g. `--model frontier`, `--privacy e2ee`).

2. **Decide local vs Venice**:
   - If estimated tokens ≤ local model's comfort window AND no capability or privacy escalation → stay local.
   - Otherwise → continue to step 3.

3. **Run the decision tree above** to pick a Venice model.

4. **Call** via [`venice-chat`](../venice-chat/SKILL.md):

   ```bash
   curl https://api.venice.ai/api/v1/chat/completions \
     -H "Authorization: Bearer $VENICE_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
       "model": "<chosen id>",
       "messages": [...],
       "venice_parameters": {"include_venice_system_prompt": false}
     }'
   ```

5. **Cap blast radius**: log the chosen model + estimated cost before sending; refuse to escalate beyond the user's `--max-cost` ceiling. When present, the response's `cost` field reports what was actually charged.

## Examples

**Example 1 — local-first wins**

Prompt: "Summarize this email in one sentence: …" (~200 tokens)

- Step 1 → local handles it. **Do not call Venice.**

**Example 2 — privacy + reasoning**

Prompt: "Here's our customer churn dataset (PII). Reason about which factors drive churn."

- Step 2 → privacy gate requires `privacy: "private"`.
- Step 4 → reasoning required → `supportsReasoning: true`.
- Step 7 → among private candidates with reasoning, pick the cheapest.
- → a private reasoning model, or an `e2ee-*` model in TEE-only mode if the user also wants attestation.

**Example 3 — multi-image vision**

Prompt: 3 product photos + "Compare these for build quality."

- Step 3 → `supportsVision && supportsMultipleImages && maxImages >= 3`.
- Step 7 → cheapest survivor, or `traits.default_vision`.

**Example 4 — frontier intelligence on a long doc**

Prompt: "Give me your absolute best take on this 400-page contract bundle." (~200K tokens)

- Step 5 → context gate drops models with `availableContextTokens` below ~200K.
- Step 6 → frontier override fires (`most_intelligent`); confirm the resolved model still passes step 5.
- → `traits.most_intelligent` (whatever the snapshot says; `grok-4-7` with 500K context as of 2026-10-02).
- Estimate cost with `pricing.extended`: as of 2026-10-02 `grok-4-7` roughly doubles its rates once input exceeds 200,000 tokens, which a ~200K prompt can cross.

**Example 5 — code agent with tools**

Prompt: "Refactor this repo. You have shell + edit tools."

- Step 4 → `supportsFunctionCalling && optimizedForCode`.
- Step 7 → cheapest survivor → `traits.default_code` if it also supports tools, else `traits.function_calling_default` filtered by `optimizedForCode`.

## Future extensions

A `scripts/route.py` CLI may be added later for runtimes that prefer structured output (`route.py --prompt '...' --max-cost 0.001 --need-vision` → `{"model_id": "...", "estimated_cost": ..., "tier": "..."}`). The prose decision tree above remains the source of truth.

Sibling routing skills (`venice-image-routing`, `venice-audio-routing`, `venice-video-routing`) can mirror this layout when needed.

## Gotchas

- **Don't hard-code model IDs.** Venice adds and retires models frequently — resolve via traits or filters against the snapshot.
- **Stale snapshot lies silently.** 30 days is the maximum age; refresh sooner if you hit a `404` on a model ID.
- **Don't route on ID prefixes.** Use `privacy`, `supportsTeeAttestation`, and `supportsE2EE`; `tee-*` IDs are unlisted legacy aliases.
- **Privacy ≠ uncensored.** `most_uncensored` / `model_spec.uncensored` and `privacy: "private"` are independent axes.
- **`most_intelligent` is not the most expensive.** It is a curated pick and can sit in a mid cost tier.
- **`enable_e2ee` defaults to `true`** on E2EE-capable models when E2EE headers are present — see [`venice-chat`](../venice-chat/SKILL.md). The routing decision selects the model; the chat skill drives the handshake.
- **Region restrictions.** `model_spec.regionRestrictions[]` (only present on restricted models) lists blocked countries → `403` for requests from those countries.
- **Trait keys differ by `type`.** Always pass `?type=text`. Don't reuse image traits.

## See also

- [`venice-models`](../venice-models/SKILL.md) — `/models`, `/models/traits`, `/models/compatibility_mapping` (the discovery API this skill consumes).
- [`venice-chat`](../venice-chat/SKILL.md) — `/chat/completions` (the call surface this skill picks a model for).
- [`venice-responses`](../venice-responses/SKILL.md) — `/responses` (no E2EE).
- [`venice-auth`](../venice-auth/SKILL.md) — Bearer vs x402 wallet auth.
- [`venice-api-keys`](../venice-api-keys/SKILL.md) — `modelPrivacy` key restrictions.
- [`venice-billing`](../venice-billing/SKILL.md) — confirming actual spend matched the routing estimate (ADMIN key).
- [`venice-errors`](../venice-errors/SKILL.md) — 402 / 403 / 422 / 429 handling on routed requests.
- Per-model snapshot: [`snapshots/text-routing.json`](snapshots/text-routing.json).
- Per-model human-readable matrix: [`routing-matrix.md`](routing-matrix.md).
