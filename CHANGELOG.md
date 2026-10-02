# Changelog

Releases are tagged `vX.Y.Z`. Pin installs to a tag; see the README.

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
