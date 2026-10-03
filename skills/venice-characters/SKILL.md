---
name: venice-characters
description: Discover and use Venice public characters (persona-driven system prompts with a suggested model). Covers GET /characters (search/filter/sort/paginate), /characters/{slug}, /characters/{slug}/reviews, the Character and Review schemas, Bearer-API-key-only auth, filter semantics (adult, pro, modelId), and how to apply a character via venice_parameters.character_slug in chat completions.
---

# Venice Characters

Characters are **published personas** on Venice — each one bundles a system prompt (plus optional context), a suggested backing model, and metadata (tags, ratings, adult / web flags). You apply a character to a chat by passing its `slug` via `venice_parameters.character_slug`.

## Use when

- You want to build a character-selection UI or discovery surface.
- You want to ship an app with a preset persona (e.g. a coding coach, a philosopher, a game NPC).
- You want to pick the right model for a character (the character's `modelId` is a suggestion; you choose the chat `model`).

Three endpoints, all tagged **Preview** (may change):

| Endpoint | Purpose |
|---|---|
| `GET /characters` | Browse/search/filter the catalog. |
| `GET /characters/{slug}` | Fetch one character. |
| `GET /characters/{slug}/reviews` | Paginated public reviews. |

**Auth: Bearer API key only.** These routes do not accept x402 / `SIGN-IN-WITH-X` (a SIWX-only request gets `401`). A request with no `Authorization` header gets a `402` x402 discovery challenge rather than `401`. There is no unauthenticated access. See [`venice-auth`](../venice-auth/SKILL.md).

## `GET /characters`

```bash
curl "https://api.venice.ai/api/v1/characters?search=philosopher&sortBy=highestRating&limit=20" \
  -H "Authorization: Bearer $VENICE_API_KEY"
```

Response: `{ "object": "list", "data": [Character, ...] }` (no total count — page with `offset` until you get fewer than `limit`).

### Query parameters

| Param | Type | Notes |
|---|---|---|
| `search` | string, ≤ 200 chars | Case-insensitive substring match on name, description, or tag. `#Tag` terms also match tags exactly (URL-encode `#` as `%23`). |
| `categories` | string[], ≤ 20 (each ≤ 100 chars) | Repeat the param or comma-separate. Matches any. |
| `tags` | string[], ≤ 20 (each ≤ 100 chars) | Repeat or comma-separate. Exact tag name, matches any. |
| `modelId` | string[], ≤ 20 (each ≤ 200 chars) | Repeat or comma-separate. Filters on the character's stored model ID — see Gotchas. |
| `isAdult` | `"true"` / `"false"` | **Exclusive**: `true` returns *only* adult characters; omitted or `false` returns only non-adult ones. |
| `isPro` | `"true"` / `"false"` | `true` = only characters whose model is a Pro model in the Venice app. `false` = no filter. Overrides `modelId` when both are sent. |
| `isWebEnabled` | `"true"` / `"false"` | `true` = only web-enabled characters. `false` = no filter. |
| `sortBy` | enum | `featured`, `highestRating`, `highlyRated`, `highlyRatedAndRecent`, `imports`, `mostRecent`, `ratingCount`. Omitted → most imports first. |
| `sortOrder` | `asc` / `desc` | Default `desc`. Only applied when `sortBy` is set. |
| `limit` | integer 1–100 | Default 50. `> 100` → `400`. |
| `offset` | integer ≥ 0 | Default 0. |

`sortBy` values that also **filter**:

- `featured` — only featured characters, ordered by imports.
- `highlyRated` — only characters with ≥ 2 ratings, ordered by average rating.
- `highlyRatedAndRecent` — only characters with at least one rating ≥ 3, ordered by creation date.
- `highestRating` (average rating), `ratingCount`, `imports`, `mostRecent` (creation date) only order.

### Character object

| Field | Notes |
|---|---|
| `id` | UUID. |
| `slug` | **Use this as `character_slug` in chat.** Same as the public ID in `venice.ai/c/<slug>`. |
| `name`, `description` | `description` may be `null`. |
| `photoUrl`, `shareUrl` | Typed nullable; `shareUrl` is `https://venice.ai/c/<slug>` (from `GET /characters/{slug}` it may also carry the author's `?ref=` referral code). |
| `author` | 5-character anonymized ID derived from the author. |
| `tags[]` | Tag names. |
| `featured`, `adult`, `webEnabled` | Booleans. |
| `modelId` | Model ID the character was built for — usually a Venice API model ID such as `venice-uncensored-1-2`, but it can be an id `/models` doesn't list; Venice's default chat model if the character has none. |
| `stats` | `{ averageRating, imports, ratingCount, ratingSum, userRating }`. Missing stats come back as `0`; `userRating` is currently always `null`. |
| `createdAt`, `updatedAt` | ISO-8601. |

## `GET /characters/{slug}`

```bash
curl "https://api.venice.ai/api/v1/characters/alan-watts" \
  -H "Authorization: Bearer $VENICE_API_KEY"
```

Returns `{ "object": "character", "data": Character }`. `404` if the character doesn't exist, isn't approved/API-visible (your own characters are exempt), or is adult while your account has the mature filter on. The path also resolves a character's UUID `id`.

## `GET /characters/{slug}/reviews`

```bash
curl "https://api.venice.ai/api/v1/characters/alan-watts/reviews?page=1&pageSize=20" \
  -H "Authorization: Bearer $VENICE_API_KEY"
```

| Param | Notes |
|---|---|
| `page` | Integer ≥ 1. Default 1. |
| `pageSize` | Integer 1–100. Default 20. |

Response (newest first; hidden reviews excluded):

```json
{
  "object": "list",
  "pagination": {"page": 1, "pageSize": 20, "total": 87, "totalPages": 5},
  "summary": {"averageRating": 4.7, "totalReviews": 87},
  "data": [
    {
      "id": "...", "characterId": "...", "createdAt": "...",
      "rating": 5, "message": "Thoughtful and grounded.",
      "locale": "en", "username": "product_user_42", "isOwner": false,
      "userAvatarUrl": "https://cdn.venice.ai/..."
    }
  ]
}
```

- `rating` is an integer 1–5; `message`, `locale`, `userAvatarUrl` may be `null`. `isOwner` is `true` for reviews written by the calling account.
- `pagination.total` counts visible reviews; `summary.totalReviews` is the character's overall rating count, so the two can differ.
- Also sets `x-pagination-limit`, `x-pagination-page`, `x-pagination-total`, `x-pagination-total-pages` headers.

## Using a character in chat

### Minimal

```json
{
  "model": "venice-uncensored-1-2",
  "venice_parameters": { "character_slug": "alan-watts" },
  "messages": [
    { "role": "user", "content": "What's the nature of mind?" }
  ]
}
```

What Venice does with the slug:

- Prepends the character's system prompt (and any character context messages) to your conversation.
- `include_venice_system_prompt` defaults to `true`; set it to `false` for a pure character voice. Characters configured with a custom system prompt turn the Venice prompt off automatically.
- Unknown or non-API-visible slug → `404 "No character could be found from the provided character_slug"`.
- **E2EE requests skip character injection** — when an E2EE model is called with the E2EE headers, the slug is silently ignored. The same model in TEE-only mode (no E2EE headers, or `enable_e2ee: false`) applies the character.

`character_slug` is also accepted in `venice_parameters` on `/responses` — see [`venice-responses`](../venice-responses/SKILL.md).

### Choosing the model

The request `model` is always what runs — Venice does **not** switch to the character's `modelId`. Use the character's `modelId` if you want the experience its author intended, or any other chat model if you need a capability it lacks (function calling, vision, reasoning):

```json
{
  "model": "kimi-k2-6",
  "venice_parameters": {
    "character_slug": "alan-watts",
    "include_venice_system_prompt": false
  },
  "messages": [...]
}
```

### Via feature suffix on the `model` string

```json
{ "model": "zai-org-glm-5-1:character_slug=alan-watts", "messages": [...] }
```

Useful when the client library (OpenAI SDK, LangChain, etc.) can't add `venice_parameters`. See [`venice-chat`](../venice-chat/SKILL.md#model-feature-suffixes) for the full suffix grammar.

## Patterns

### Character picker UI

```ts
const res = await fetch(`${base}/characters?sortBy=featured&limit=50`, {
  headers: { Authorization: `Bearer ${process.env.VENICE_API_KEY}` },
})
const { data } = await res.json()
// show data[].photoUrl, data[].name, data[].stats.averageRating
// pick a character, then pass its slug (and its modelId if it appears in GET /models) into chat:
await chat({
  model: picked.modelId,
  venice_parameters: { character_slug: picked.slug },
  messages: [...]
})
```

### Web-enabled, family-friendly, recent and well-rated

```bash
/characters?isWebEnabled=true&sortBy=highlyRatedAndRecent
```

(Non-adult is already the default; `isAdult=false` is redundant.)

### Search by hashtag

```bash
/characters?search=%23Philosophy
```

## Errors

| Code | Meaning |
|---|---|
| `400` | Bad query params (e.g. `limit > 100`, `pageSize > 100`, unknown `sortBy`, `search` > 200 chars, > 20 array items). |
| `401` | Unknown, expired or revoked API key, or SIWX-only auth (not supported here). |
| `402` | No `Authorization` header — x402 discovery challenge. Send a Bearer key. |
| `404` | Unknown / unapproved / hidden slug (also adult characters when the account's mature filter is on). |
| `429` | Too many failed requests (the error-rate limiter). |
| `500` | Transient. Retry. |

## Gotchas

- This is a **Preview API** — response shape may change.
- Slugs are the **public ID** on the character's page (`venice.ai/c/<slug>`); they are not the `id` UUID (though both resolve).
- **`isAdult` is exclusive, not additive.** You can't get adult and non-adult characters in one list call. If the account behind the key has the mature filter enabled, adult characters are never returned, even with `isAdult=true`.
- **`modelId` filter vs. `modelId` field.** For some models, filtering by the API model ID may return nothing even though characters built for that model exist — fall back to filtering `data[].modelId` client-side.
- `modelId` on a character is a suggestion. If you reuse it, it may be Pro-only, offline, or not an API model at all — handle `404 "Specified model not found"`, `401 "only available to Pro users"` and `503` from chat and fall back to another model.
- `photoUrl` / `shareUrl` / `description` are typed nullable — don't assume they exist.
