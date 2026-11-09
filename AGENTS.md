# Agent guide — venice-skills

This repo is the **authoritative Venice API reference**, kept in sync with the Venice OpenAPI spec. When you build anything that touches the Venice API — guides, code samples, sandboxes, scripts — **load the relevant skill instead of guessing** endpoints, params, or model slugs.

## Read this first

- **`README.md`** — the full skill catalog and how the format works.
- **`skills/<name>/SKILL.md`** — one self-contained reference per API surface (auth, chat, image, video, audio, embeddings, billing, errors, etc.).

## How to use

1. Pick the skill matching the surface you're documenting (e.g. `venice-image-generate`, `venice-video`, `venice-chat`, `venice-text-routing`).
2. Treat its endpoint tables, params, and curl/SDK examples as the source of truth.
3. If a skill looks stale vs. the live API, **flag it** — don't invent. `scripts/sync_from_swagger.py` checks for drift against the spec.

## Authoring

New skill? Copy `template/SKILL.template.md` to `skills/<name>/SKILL.md` and follow `CONTRIBUTING.md`.

> Source of truth: the Venice OpenAPI spec + public docs at https://docs.venice.ai. For the broader product/surface picture (every endpoint mapped to user actions), see the sibling `venice-kb/` repo.
