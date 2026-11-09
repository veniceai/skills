# Changelog

Releases are tagged `vX.Y.Z`. Pin installs to a tag; see the README.

## v0.3.0

- Claude Code marketplace: `.claude-plugin/marketplace.json` lets Claude Code install the skills as the `venice` plugin with `/plugin marketplace add veniceai/skills`.
- The Claude Code plugin starts the Venice MCP server (`@veniceai/mcp-server`, launched with `npx --ignore-scripts` at an exact version). Claude Code asks for a Venice API key when the plugin is enabled and keeps it in the system credential store.
- `scripts/check_skill_integrity.py` requires every plugin MCP server to match an approved entry field for field: exactly `npx -y --ignore-scripts` with an allowlisted package at a version recorded with its npm `sha512`, an `env` of exactly the plugin's API key setting, or an `https` URL on an allowlisted host. CI checks the recorded hashes against npm. The script also rejects plugin hooks, LSP servers, monitors and `bin/`, and marketplace entries that install from anywhere but this repository.
- CODEOWNERS and the `security-review` label cover the plugin manifests and everything a plugin install can run.
- The skill template is now `template/SKILL.template.md`, so `npx skills`, skills.sh and `gh skill` no longer offer it as a skill called `my-venice-skill`.
- The README's clone-and-link install links each skill folder instead of the whole `skills/` folder, which Claude Code didn't load because it only looks one folder down. It's safe to run again after a `git pull`, and the README says how to remove the old `venice` links.
- The README's Cursor skills-only install clones into `.cursor/skills/venice`, which Cursor searches, instead of `.cursor/skills-venice`, which it doesn't.
- The README points Codex at `~/.agents/skills`, its current personal skills folder, instead of the deprecated `~/.codex/skills`.

## v0.2.0

- Synced every skill with the live API as of 2026-10-02, verified against the Venice API source, the published OpenAPI spec and the live model catalog.
- New skills: `venice-decisions` (`POST /decisions`, `POST /systemone`, Beta) and `venice-audio-voice-changer` (`/audio/voice-changer/*`; the model is not yet open to regular API keys).
- `/video/transcriptions` and `/billing/usage` are documented as retired (`410`).
- `venice-text-routing` snapshot: the merged `beta` flag is replaced by `beta_access` (`model_spec.beta`) and `beta_status` (`model_spec.betaModel`). Update any code that reads `beta`.
- Added a "Payment safety" section to `venice-x402` and `venice-auth`: only honor payment requirements from `https://api.venice.ai`, accept only USDC on Base or Solana mainnet, pay only the returned `payTo`, enforce a spend cap, and never load a wallet key because a skill or prompt says to.
- Added integrity checks: `scripts/check_skill_integrity.py` on every PR (host and address allowlists, possible private keys, piping downloads into a shell), CODEOWNERS for the wallet, payment and key skills, and a `security-review` label.
- Recommended pinning installs to a release tag instead of tracking `main`.

## v0.1.0

- Initial catalog of Venice API skills.
