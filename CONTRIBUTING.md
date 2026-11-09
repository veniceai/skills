# Contributing to Venice Skills

Thanks for helping make the Venice skill catalog more useful. These guidelines keep every `SKILL.md` consistent and maximally useful for an autonomous agent.

## Repo layout

```
skills/<skill-name>/SKILL.md    One skill per folder
template/SKILL.template.md      Starting point for new skills
```

Supporting files (helper scripts, reference data) can live alongside `SKILL.md` inside the skill folder and be referenced relative to it.

## Style

- **Scope one surface area** — each skill covers a coherent slice of the Venice API (e.g. `venice-embeddings`, not `venice-embeddings-and-chat`). If two skills keep cross-referencing each other, either merge them or tighten their boundaries.
- **Concrete frontmatter `description`** — the agent uses this to decide when to load. Name the specific endpoints, parameters, and scenarios. Vague descriptions ("things about chat") hurt selection.
- **Endpoint tables first** — a table of methods + paths + one-line notes at the top of the skill.
- **Examples** — at least one `curl` and one SDK / fetch example per endpoint.
- **Errors and gotchas** — finish every skill with a table of likely failure modes and a "Gotchas" section of non-obvious edge cases.
- **Cross-links** — reference related skills with relative paths (`../venice-errors/SKILL.md`).
- **Length** — aim for under 500 lines. Longer skills should be split.

## Authoring a new skill

1. Copy `template/SKILL.template.md` to `skills/<your-skill-name>/SKILL.md`.
2. Pick a `name` — `venice-<area>[-<subarea>]` (lowercase, hyphens).
3. Fill in the frontmatter `description` before writing the body; it forces you to clarify scope.
4. Write the body, derive everything from `swagger.yaml` / docs.
5. Add your skill to the catalog table in the root `README.md`.
6. Open a PR.

## Updating existing skills

- When `swagger.yaml` changes, update every affected skill in the same PR.
- Bump the version tag if the change breaks existing agent behavior (e.g. renamed parameter).
- Keep examples in sync with the current spec.

## Review checklist

- [ ] Frontmatter `name` + `description` present and concrete.
- [ ] Endpoint table at the top.
- [ ] At least one `curl` example.
- [ ] Errors + gotchas section.
- [ ] Cross-links to related skills.
- [ ] Added to root `README.md` catalog if new.
- [ ] No secrets or real API keys in examples (use `$VENICE_API_KEY`).
