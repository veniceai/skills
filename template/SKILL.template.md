---
name: my-venice-skill
description: One or two sentences describing exactly when an agent should load this skill and what it covers. Mention the specific endpoints, parameters, or scenarios so the agent can confidently pick it — vague descriptions hurt skill selection.
---

# My Venice skill

One-paragraph summary of what this skill teaches the agent. Focus on which Venice API surface it maps to and when to prefer it over related skills.

## Endpoints

| Method | Path | Notes |
|---|---|---|
| `POST` | `/example` | Required params, authentication, cost model. |

## Quick start

```bash
curl -X POST https://api.venice.ai/api/v1/example \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{ "foo": "bar" }'
```

```ts
// SDK or fetch example
```

## Parameters

### Required

- `field_a` — what it is, valid range, default.

### Optional

- `field_b` — …

## Response

```json
{
  "example": "response"
}
```

## Errors

| Status | Cause | Fix |
|---|---|---|
| `400` | Bad input | Validate against the schema. |
| `429` | Rate limit | Back off with jitter. |

## Gotchas

- Specific edge cases, rate-limit caps, model constraints.
- Cross-links to related skills: [`venice-errors`](../venice-errors/SKILL.md), [`venice-billing`](../venice-billing/SKILL.md), etc.
