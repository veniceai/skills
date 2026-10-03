#!/usr/bin/env python3
"""Refresh the venice-text-routing snapshot + matrix from the live API.

Hits ``GET /models?type=text`` and ``GET /models/traits?type=text``, normalizes
the response to a routing-shaped subset, and rewrites two files in the parent
skill folder:

  - ``snapshots/text-routing.json`` — machine-readable snapshot the agent reads
    at routing time. Includes ``snapshot_date`` so the agent can detect
    staleness.
  - ``routing-matrix.md`` — human-readable per-model table grouped by cost
    tier (XS / S / M / L / Frontier) plus TEE/E2EE buckets.

Usage:
    python scripts/refresh_routing.py                  # no key needed
    VENICE_API_KEY=sk-... python scripts/refresh_routing.py   # optional; tailors to the key
    python scripts/refresh_routing.py --base-url https://api.venice.ai
    python scripts/refresh_routing.py --dry-run        # don't write files

Stdlib only — no third-party deps. CI-safe.

Exit codes:
  0  success
  1  HTTP / parse / write failure
  2  no text models returned (the API responded but the catalog was empty —
     treat as drift; do not overwrite the existing snapshot)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_BASE_URL = "https://api.venice.ai"
SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
SNAPSHOT_PATH = SKILL_DIR / "snapshots" / "text-routing.json"
MATRIX_PATH = SKILL_DIR / "routing-matrix.md"

# Cost-tier bucket boundaries, in USD per 1M input tokens.
# Output-token cost is roughly 2-3x input cost across the catalog, so input is
# the cleaner sort key. Each bucket excludes its upper bound.
TIERS: list[tuple[str, float]] = [
    ("XS", 0.20),
    ("S", 1.00),
    ("M", 4.00),
    ("L", 10.00),
    ("Frontier", float("inf")),
]

# Capability flags surfaced as columns in the matrix, in display order.
# (column_label, capability_key)
CAPABILITY_COLUMNS: list[tuple[str, str]] = [
    ("vis", "supportsVision"),
    ("multi", "supportsMultipleImages"),
    ("aud", "supportsAudioInput"),
    ("vid", "supportsVideoInput"),
    ("rsn", "supportsReasoning"),
    ("eff", "supportsReasoningEffort"),
    ("tool", "supportsFunctionCalling"),
    ("code", "optimizedForCode"),
    ("web", "supportsWebSearch"),
    ("xs", "supportsXSearch"),
    ("js", "supportsResponseSchema"),
    ("tee", "supportsTeeAttestation"),
    ("e2ee", "supportsE2EE"),
]


def fetch_json(url: str, api_key: str | None) -> dict[str, Any]:
    headers = {
        "Accept": "application/json",
        "User-Agent": "venice-text-routing-refresh/0.1",
    }
    # Both endpoints are public. A key only tailors the result (e.g. a
    # modelPrivacy-restricted key filters the catalog), so it is optional.
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def tier_for_input_price(usd_per_1m: float | None) -> str:
    """Bucket a model into XS / S / M / L / Frontier by input price."""
    if usd_per_1m is None:
        return "unknown"
    for label, upper in TIERS:
        if usd_per_1m < upper:
            return label
    return "Frontier"


def privacy_label(capabilities: dict[str, Any], raw_privacy: str | None) -> str:
    """Resolve the routing privacy label.

    ``model_spec.privacy`` is only ever ``private`` or ``anonymized``; the
    TEE/E2EE tiers come from the capability flags, which win over it.
    """
    if capabilities.get("supportsE2EE"):
        return "e2ee"
    if capabilities.get("supportsTeeAttestation"):
        return "tee"
    return raw_privacy or "unknown"


def normalize_model(entry: dict[str, Any]) -> dict[str, Any]:
    spec = entry.get("model_spec") or entry.get("modelSpec") or {}
    capabilities = spec.get("capabilities") or {}
    pricing = spec.get("pricing") or {}
    input_usd: float | None = None
    output_usd: float | None = None
    if isinstance(pricing.get("input"), dict):
        input_usd = pricing["input"].get("usd")
    if isinstance(pricing.get("output"), dict):
        output_usd = pricing["output"].get("usd")

    model_id = entry.get("id") or ""
    return {
        "id": model_id,
        "tier": tier_for_input_price(input_usd),
        "privacy": privacy_label(capabilities, spec.get("privacy")),
        "capabilities": {
            key: bool(capabilities.get(key))
            for _, key in CAPABILITY_COLUMNS
        },
        "max_images": capabilities.get("maxImages"),
        "available_context_tokens": spec.get("availableContextTokens"),
        "max_completion_tokens": spec.get("maxCompletionTokens"),
        "pricing_per_1m": {
            "input_usd": input_usd,
            "output_usd": output_usd,
        },
        "beta_access": bool(spec.get("beta")),
        "beta_status": bool(spec.get("betaModel")),
        "offline": bool(spec.get("offline")),
        "region_restrictions": spec.get("regionRestrictions") or [],
        "deprecation_date": (spec.get("deprecation") or {}).get("date"),
    }


def write_snapshot(models: list[dict[str, Any]], traits: dict[str, str], base_url: str, snapshot_date: str) -> None:
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "snapshot_date": snapshot_date,
        "source": {
            "models": f"GET {base_url.rstrip('/')}/api/v1/models?type=text",
            "traits": f"GET {base_url.rstrip('/')}/api/v1/models/traits?type=text",
        },
        "tier_boundaries_usd_per_1m_input": {
            label: (None if upper == float("inf") else upper)
            for label, upper in TIERS
        },
        "traits": traits,
        "models": sorted(models, key=lambda m: (m["tier"], m["id"])),
    }
    SNAPSHOT_PATH.write_text(
        json.dumps(payload, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def fmt_cap(model: dict[str, Any], key: str) -> str:
    return "✓" if model["capabilities"].get(key) else "-"


def fmt_ctx(model: dict[str, Any]) -> str:
    ctx = model.get("available_context_tokens")
    if not isinstance(ctx, int) or ctx <= 0:
        return "?"
    if ctx >= 1_000_000:
        return f"{ctx // 1000}K" if ctx % 1_000_000 else f"{ctx // 1_000_000}M"
    if ctx >= 1000:
        return f"{ctx // 1000}K"
    return str(ctx)


def fmt_price(model: dict[str, Any]) -> str:
    p = model["pricing_per_1m"]
    parts: list[str] = []
    if p.get("input_usd") is not None:
        parts.append(f"in ${p['input_usd']:.2f}")
    if p.get("output_usd") is not None:
        parts.append(f"out ${p['output_usd']:.2f}")
    return ", ".join(parts) if parts else "?"


MATRIX_HEADER = (
    "| id | privacy | "
    + " | ".join(label for label, _ in CAPABILITY_COLUMNS)
    + " | ctx | $/1M |\n"
    + "|---|---|"
    + "|".join(["---"] * len(CAPABILITY_COLUMNS))
    + "|---|---|"
)


def render_section(title: str, blurb: str, models: list[dict[str, Any]], empty: str = "_No models in the current snapshot._") -> str:
    if not models:
        return f"### {title}\n\n{blurb}\n\n{empty}\n"
    rows = [MATRIX_HEADER]
    for m in sorted(models, key=lambda m: m["id"]):
        cells = (
            [m["id"], m["privacy"]]
            + [fmt_cap(m, key) for _, key in CAPABILITY_COLUMNS]
            + [fmt_ctx(m), fmt_price(m)]
        )
        cells[0] = f"`{m['id']}`" + (f" (deprecated {m['deprecation_date'][:10]})" if m["deprecation_date"] else "")
        rows.append("| " + " | ".join(cells) + " |")
    return f"### {title}\n\n{blurb}\n\n" + "\n".join(rows) + "\n"


def write_matrix(models: list[dict[str, Any]], traits: dict[str, str], snapshot_date: str) -> None:
    by_tier: dict[str, list[dict[str, Any]]] = {label: [] for label, _ in TIERS}
    by_tier["unknown"] = []
    tee_models: list[dict[str, Any]] = []
    e2ee_models: list[dict[str, Any]] = []
    for m in models:
        if m["privacy"] == "tee":
            tee_models.append(m)
        elif m["privacy"] == "e2ee":
            e2ee_models.append(m)
        else:
            by_tier.setdefault(m["tier"], []).append(m)

    sections = [
        ("XS — `< $0.20` input per 1M", "Cheapest path; classification, intent extraction, simple summarization.", by_tier.get("XS", [])),
        ("S — `$0.20 – < $1` input per 1M", "General chat, basic agents, light vision.", by_tier.get("S", [])),
        ("M — `$1 – < $4` input per 1M", "Reasoning at moderate depth, strong code, multi-image vision.", by_tier.get("M", [])),
        ("L — `$4 – < $10` input per 1M", "Heavy reasoning, complex tool use.", by_tier.get("L", [])),
        ("Frontier — `≥ $10` input per 1M", "Best-available. Resolve via trait `most_intelligent`.", by_tier.get("Frontier", [])),
        ("Unpriced", "No input price in `/models`.", by_tier["unknown"], "_No unpriced models in the current snapshot._"),
        (
            "TEE — hardware-attested",
            "Verify via `GET /api/v1/tee/attestation`.",
            tee_models,
            "_No TEE-only models in the current snapshot. TEE calls use the E2EE models below with the E2EE headers omitted._",
        ),
        ("E2EE — end-to-end encrypted", "Requires ECDH (secp256k1) / HKDF / AES-256-GCM handshake. See [`venice-chat`](../venice-chat/SKILL.md).", e2ee_models),
    ]

    trait_rows = "\n".join(
        f"| `{trait}` | `{model_id}` |" for trait, model_id in sorted(traits.items())
    ) or "| _none returned_ | _none_ |"

    body = (
        "# Venice text-model routing matrix\n\n"
        "> **Auto-generated by [`scripts/refresh_routing.py`](scripts/refresh_routing.py).** Do not hand-edit.\n>\n"
        f"> Snapshot date: `{snapshot_date}` — sourced from `GET /api/v1/models?type=text` + `GET /api/v1/models/traits?type=text`.\n>\n"
        "> Authoritative machine-readable form: [`snapshots/text-routing.json`](snapshots/text-routing.json).\n\n"
        "## Cost tiers\n\n"
        "| Tier | $/1M input tokens |\n"
        "|---|---|\n"
        "| XS | < $0.20 |\n"
        "| S | $0.20 – < $1 |\n"
        "| M | $1 – < $4 |\n"
        "| L | $4 – < $10 |\n"
        "| Frontier | ≥ $10 |\n\n"
        "Buckets are this skill's own convention, keyed on input price only; output prices vary widely within a bucket.\n\n"
        "## Trait shortcuts\n\n"
        "| Trait | Resolves to |\n|---|---|\n"
        f"{trait_rows}\n\n"
        "## Models\n\n"
        "Capability column legend: "
        + ", ".join(f"`{label}` = `{key}`" for label, key in CAPABILITY_COLUMNS)
        + ", `ctx` = `availableContextTokens`, `$/1M` = input/output USD per 1M tokens.\n\n"
        "`-` = not supported / not advertised.\n\n"
    )
    body += "\n".join(render_section(*section) for section in sections)
    body += (
        "\n## Sanity filters applied at routing time\n\n"
        "- Drop models with `beta_access` (`model_spec.beta`) unless your key has beta access. "
        "`beta_status` (`model_spec.betaModel`) models are callable but may change or disappear; prefer non-beta when tied.\n"
        "- Drop models with `model_spec.offline === true`.\n"
        "- Drop models whose `model_spec.regionRestrictions` list the caller's country.\n"
        "- Prefer models without `model_spec.deprecation` (marked `deprecated <date>` above).\n"
    )
    MATRIX_PATH.write_text(body, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default=os.environ.get("VENICE_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--api-key", default=os.environ.get("VENICE_API_KEY"))
    parser.add_argument("--dry-run", action="store_true", help="Fetch + normalize but don't write files.")
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    models_url = f"{base}/api/v1/models?type=text"
    traits_url = f"{base}/api/v1/models/traits?type=text"

    try:
        models_payload = fetch_json(models_url, args.api_key)
    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        print(f"ERROR: failed to fetch {models_url}: {e}", file=sys.stderr)
        return 1

    try:
        traits_payload = fetch_json(traits_url, args.api_key)
    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        print(f"ERROR: failed to fetch {traits_url}: {e}", file=sys.stderr)
        return 1

    raw_models = models_payload.get("data") or []
    if not raw_models:
        print(f"ERROR: {models_url} returned 0 models — refusing to overwrite snapshot", file=sys.stderr)
        return 2

    models = [normalize_model(m) for m in raw_models if m.get("id")]
    traits_data = traits_payload.get("data") or {}
    traits = {k: str(v) for k, v in traits_data.items() if isinstance(v, str)}

    print(f"Fetched {len(models)} text models, {len(traits)} traits.")

    if args.dry_run:
        json.dump(
            {"models_count": len(models), "traits_count": len(traits)},
            sys.stdout,
            indent=2,
        )
        sys.stdout.write("\n")
        return 0

    snapshot_date = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    write_snapshot(models, traits, base, snapshot_date)
    write_matrix(models, traits, snapshot_date)

    print(f"Wrote {SNAPSHOT_PATH.relative_to(SKILL_DIR.parent.parent)}")
    print(f"Wrote {MATRIX_PATH.relative_to(SKILL_DIR.parent.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
