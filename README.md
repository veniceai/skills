# Venice Skills

Agent Skills for the [Venice API](https://docs.venice.ai). Skills are self-contained folders of instructions (one `SKILL.md` each) that an LLM agent loads on demand to work correctly against a specific surface area of the API.

This repository is the canonical source of truth for Venice skills and is kept in sync with [`swagger.yaml`](https://docs.venice.ai). Use it with Cursor, Claude, Codex, Cline, or any other agent runtime that supports the Agent Skills format.

## What's in here

```
skills/        One folder per skill, each with a SKILL.md
template/      Copy this as a starting point for a new skill
```

## Skill catalog

| Skill | Covers |
|---|---|
| [`venice-api-overview`](./skills/venice-api-overview/SKILL.md) | Base URL, auth modes, response headers, pricing model, versioning |
| [`venice-auth`](./skills/venice-auth/SKILL.md) | Bearer API keys + SIWX / x402 wallet authentication (Base and Solana) |
| [`venice-chat`](./skills/venice-chat/SKILL.md) | `/chat/completions` — `venice_parameters`, multimodal, tools, reasoning, streaming |
| [`venice-responses`](./skills/venice-responses/SKILL.md) | `/responses` — OpenAI-compatible Responses API (Alpha) |
| [`venice-embeddings`](./skills/venice-embeddings/SKILL.md) | `/embeddings` — models, encoding formats, dimensions |
| [`venice-image-generate`](./skills/venice-image-generate/SKILL.md) | `/image/generate`, `/images/generations`, `/image/styles` |
| [`venice-image-edit`](./skills/venice-image-edit/SKILL.md) | `/image/edit`, `/image/multi-edit`, `/image/upscale`, `/image/background-remove` |
| [`venice-audio-speech`](./skills/venice-audio-speech/SKILL.md) | `/audio/speech`, `/audio/voices` — TTS models, voices, voice cloning, formats, streaming |
| [`venice-audio-music`](./skills/venice-audio-music/SKILL.md) | `/audio/quote`, `/audio/queue`, `/audio/retrieve`, `/audio/complete` |
| [`venice-audio-voice-changer`](./skills/venice-audio-voice-changer/SKILL.md) | `/audio/voice-changer/*` — async speech-to-speech voice conversion (no model open to regular API keys yet) |
| [`venice-audio-transcription`](./skills/venice-audio-transcription/SKILL.md) | `/audio/transcriptions` — Whisper, Parakeet, Scribe, Wizper, xAI STT |
| [`venice-video`](./skills/venice-video/SKILL.md) | `/video/quote`, `/video/queue`, `/video/retrieve`, `/video/complete` (`/video/transcriptions` is retired) |
| [`venice-decisions`](./skills/venice-decisions/SKILL.md) | `/decisions` and `/systemone` — typed judgments from the Jev decision model (Beta) |
| [`venice-models`](./skills/venice-models/SKILL.md) | `/models`, `/models/traits`, `/models/compatibility_mapping` |
| [`venice-text-routing`](./skills/venice-text-routing/SKILL.md) | Pick a Venice text model by privacy tier (anonymized / private / TEE / E2EE), capability (vision, reasoning, code, tools, web search), context size, and cost. The routing layer above `/chat/completions`. |
| [`venice-characters`](./skills/venice-characters/SKILL.md) | `/characters*` + `venice_parameters.character_slug` |
| [`venice-api-keys`](./skills/venice-api-keys/SKILL.md) | CRUD `/api_keys`, rate limits, Web3 key generation |
| [`venice-billing`](./skills/venice-billing/SKILL.md) | `/billing/balance`, `/billing/usage-history`, `/billing/usage-analytics` |
| [`venice-x402`](./skills/venice-x402/SKILL.md) | `/x402/*` — wallet credits, USDC on Base and Solana |
| [`venice-crypto-rpc`](./skills/venice-crypto-rpc/SKILL.md) | `/crypto/rpc/*` — EVM / Starknet / Solana JSON-RPC proxy with 1×/2×/4× pricing |
| [`venice-augment`](./skills/venice-augment/SKILL.md) | `/augment/text-parser`, `/augment/scrape`, `/augment/search` |
| [`venice-errors`](./skills/venice-errors/SKILL.md) | Error shapes, 402 payment required, 422 content policy, 429 rate limits, retry strategy |

## Using these skills

Each skill is just a folder with a `SKILL.md` that starts with YAML frontmatter:

```yaml
---
name: venice-chat
description: …when the agent should load this skill and what's in it…
---
```

### Cursor

Clone or subtree the repo and point your agent skills path at `skills/`:

```bash
# project-local, pinned to a release
git clone --branch v0.2.0 git@github.com:veniceai/skills.git .cursor/skills-venice
# or copy individual skills
cp -r skills/venice-chat .cursor/skills/
```

### Claude / Codex / OpenCode / Hermes / other runtimes

The `SKILL.md` format is a shared spec — drop the `skills/` folder (or any subset) into whichever path your runtime watches:

| Runtime | Project-local | Global |
|---|---|---|
| Claude Code | `.claude/skills/` | `~/.claude/skills/` |
| Codex | `.codex/skills/` | `$CODEX_HOME/skills/` (default `~/.codex/skills/`) |
| OpenCode | `.opencode/skills/` (also reads `.claude/skills/` + `.agents/skills/`) | `~/.config/opencode/skills/` |
| Hermes Agent (Nous Research) | `$HERMES_OPTIONAL_SKILLS_DIR` | `~/.hermes/skills/` |
| Cursor | `.cursor/skills/` | `~/.cursor/skills/` |
| Cline | `.clinerules/skills/` | n/a |
| Any other runtime | `.agents/skills/` (convention) | `~/.agents/skills/` |

One-liner install for most setups:

```bash
# clone once, pinned to a release
git clone --branch v0.2.0 https://github.com/veniceai/skills.git ~/src/venice-skills

# symlink into every runtime you use
ln -s ~/src/venice-skills/skills ~/.claude/skills/venice
ln -s ~/src/venice-skills/skills ~/.codex/skills/venice
ln -s ~/src/venice-skills/skills ~/.config/opencode/skills/venice
ln -s ~/src/venice-skills/skills ~/.hermes/skills/venice
```

### Pin to a release

A single clone feeds every runtime you symlink it into, and some skills teach an agent to sign USDC payments and handle wallet keys. Pin to a release tag rather than tracking `main`, and upgrade deliberately after reading the [changelog](./CHANGELOG.md):

```bash
cd ~/src/venice-skills
git fetch --tags
git diff v0.2.0 <new-tag> -- skills/   # review what changed
git checkout <new-tag>
```

The agent discovers each `SKILL.md` by its frontmatter `name` + `description` and loads it on demand. Runtimes that define extra frontmatter fields (`version`, `platforms`, `metadata.*`, `compatibility`, …) are required by spec to **ignore unknown fields**, so the same skill file works everywhere without forks.

> **NanoCoder** and similar minimal coding agents (Claw-Code, etc.) don't ship their own skills runtime — they piggyback on whichever host agent (Claude Code, OpenCode, Hermes) is driving them. Install the skills in the host and NanoCoder will see them automatically.

### As a git submodule

```bash
git submodule add git@github.com:veniceai/skills.git vendor/venice-skills
git -C vendor/venice-skills checkout v0.2.0
```

Then symlink or copy the subsets you want into your agent's skill path.

## Authoring a new skill

1. Copy `template/` to `skills/<your-skill-name>/`.
2. Fill in the frontmatter and body. Keep the `description` concrete — it's what an agent uses to decide when to load the skill.
3. Link related skills at the bottom of the `SKILL.md` for cross-navigation.
4. Open a PR.

See [`CONTRIBUTING.md`](./CONTRIBUTING.md) for style conventions (short first paragraph, explicit endpoint tables, curl + one SDK example, "gotchas" section, ≤ 500 lines).

## Source of truth

Skills are derived from the current Venice OpenAPI spec and public docs at <https://docs.venice.ai>. When the spec changes, update the affected skills and cut a release.

## Authentication quick reference

| Mode | Header | When to use |
|---|---|---|
| **Bearer API key** | `Authorization: Bearer <key>` | Venice account; each request is charged to one currency, in the order DIEM → earned credits → bundled credits → USD. |
| **x402 / SIWX wallet** | `SIGN-IN-WITH-X: <base64 SIWX>` | No account required, pay per request with USDC on Base (chain `8453`) or Solana mainnet. The legacy `X-Sign-In-With-X` name still works. |

See [`skills/venice-auth`](./skills/venice-auth/SKILL.md) for full signing details.

## Staying in sync with the API

The skills are derived from the Venice OpenAPI spec. Run the sync script to diff the currently-published spec against the endpoints and model-type enums referenced in each `SKILL.md`:

```bash
python scripts/sync_from_swagger.py --spec https://api.venice.ai/api/v1/swagger.yaml
# or against a local copy
python scripts/sync_from_swagger.py --spec ./swagger.yaml
```

The script prints:

- endpoints in the spec that no skill references yet,
- endpoints referenced in skills but missing from the spec (stale docs),
- model-type enum drift (e.g. new `type=…` value added).

CI runs this nightly; any drift is filed as an issue with the `sync` label.

## Integrity checks

Some skills teach an agent to sign USDC payments, hold wallet keys, manage API keys and send JSON-RPC to mainnets, so every change is gated before it can reach an install:

- **`scripts/check_skill_integrity.py`** runs on every PR and fails if the added lines introduce a host outside its allowlist, a wallet address other than the known USDC contracts and Solana mainnet id, a possible private key, or a pipe-to-shell pattern. Run it locally with `python scripts/check_skill_integrity.py --base origin/main`. Extending an allowlist means editing that script, which needs a code-owner review.
- **CODEOWNERS** requires a review from `@veniceai/api-reviewers` for `venice-x402`, `venice-auth`, `venice-api-keys`, `venice-crypto-rpc`, `scripts/` and `.github/`, and those PRs are labeled `security-review`.
- **Releases** are tagged; see [Pin to a release](#pin-to-a-release) and the [changelog](./CHANGELOG.md).

## License

MIT — see [`LICENSE`](./LICENSE). Use these skills however you like; a credit link back to <https://docs.venice.ai> is appreciated but not required.
