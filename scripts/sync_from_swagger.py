#!/usr/bin/env python3
"""Diff the Venice OpenAPI spec against the skills in this repo.

Given a swagger URL or local path, the script reports:

  1. Endpoints that exist in the spec but are not referenced in any SKILL.md.
  2. Endpoints referenced in SKILL.md files that no longer exist in the spec.
  3. Values of enum fields we care about (e.g. `/models` `type=…`) and whether
     every value appears in at least one skill.
  4. A short manifest of every endpoint and which skill(s) document it.

Exit code is `0` when everything matches, `1` when drift is detected — wire
into CI to auto-file an issue.

Usage:
    python scripts/sync_from_swagger.py --spec https://api.venice.ai/api/v1/swagger.yaml
    python scripts/sync_from_swagger.py --spec ./swagger.yaml
    python scripts/sync_from_swagger.py --spec ./swagger.yaml --json > report.json

Requires: pyyaml (``pip install pyyaml``).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any
from urllib.request import urlopen

try:
    import yaml  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover
    print(
        "error: pyyaml is required. Install with `pip install pyyaml`.",
        file=sys.stderr,
    )
    sys.exit(2)


REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"

# Enums in the spec we want to track for drift. Keyed by a human label;
# value is a list of JSONPath-ish steps through the parsed spec.
TRACKED_ENUMS: dict[str, list[str]] = {
    "models.type": [
        "paths",
        "/models",
        "get",
        "parameters",
        "type",
        "schema",
        "enum",
    ],
}

# Paths we never expect a skill to reference verbatim (health checks etc).
PATH_IGNORE = re.compile(r"^/$|^/health$|^/ping$")

# Live, publicly documented endpoints that are deliberately absent from
# swagger.yaml. Without this list they report as [STALE] forever, which trains
# readers to ignore the stale section. Drop an entry the moment the spec picks
# the path up; the assertion below fails loudly if that happens.
UNSPECCED_LIVE_PATHS = {
    "/tee/attestation",
    "/tee/signature",
}


def load_spec(src: str) -> dict[str, Any]:
    if src.startswith("http://") or src.startswith("https://"):
        with urlopen(src) as fh:  # noqa: S310 - trusted CI input
            raw = fh.read().decode("utf-8")
    else:
        raw = Path(src).read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        raise SystemExit(f"spec at {src} is not a YAML/JSON object")
    return data


def spec_paths(spec: dict[str, Any]) -> list[str]:
    return sorted(p for p in spec.get("paths", {}) if not PATH_IGNORE.match(p))


def walk(data: Any, steps: list[str]) -> Any:
    cur = data
    for step in steps:
        if isinstance(cur, list):
            match = next(
                (
                    item
                    for item in cur
                    if isinstance(item, dict) and item.get("name") == step
                ),
                None,
            )
            if match is None:
                return None
            cur = match
        elif isinstance(cur, dict):
            if step not in cur:
                return None
            cur = cur[step]
        else:
            return None
    return cur


HTTP_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS")
ENDPOINT_PATTERN = re.compile(
    r"`(?:(?:" + "|".join(HTTP_METHODS) + r")\s+)?(/[A-Za-z0-9_\-/{}\.]+)`"
)
TYPE_ENUM_PATTERN = re.compile(r"\btype=([A-Za-z0-9_\-]+)")


def read_skill_refs() -> tuple[dict[str, set[str]], set[str]]:
    """Return (endpoint -> skill set, all enum tokens seen in skills)."""
    endpoint_refs: dict[str, set[str]] = defaultdict(set)
    enum_tokens: set[str] = set()

    for skill_md in SKILLS_DIR.rglob("SKILL.md"):
        text = skill_md.read_text(encoding="utf-8")
        skill = skill_md.parent.name
        for path in ENDPOINT_PATTERN.findall(text):
            path = path.rstrip("/.")
            # Spec paths are relative to the `/api/v1` base; strip it when
            # skills document the full URL-style path.
            if path.startswith("/api/v1"):
                path = path[len("/api/v1"):] or "/"
            if path and path != "/":
                endpoint_refs[path].add(skill)
        for tok in TYPE_ENUM_PATTERN.findall(text):
            enum_tokens.add(tok.lower())
    return endpoint_refs, enum_tokens


def diff(spec: dict[str, Any]) -> dict[str, Any]:
    spec_endpoints = set(spec_paths(spec))
    endpoint_refs, enum_tokens_in_skills = read_skill_refs()
    skill_endpoints = set(endpoint_refs)

    missing_in_skills = sorted(spec_endpoints - skill_endpoints)

    def _is_real_stale(p: str) -> bool:
        # Only count as stale if it looks like a real endpoint (≥2 segments,
        # no literal "..." placeholders) AND is not a prefix of a spec path.
        if "..." in p or p.count("/") < 2:
            return False
        if p in UNSPECCED_LIVE_PATHS:
            return False
        if any(spec_path.startswith(p + "/") for spec_path in spec_endpoints):
            return False
        # Normalize {var} placeholders so skill refs with different param
        # names still match the spec (e.g. /x402/balance/{wallet} vs
        # /x402/balance/{walletAddress}).
        normalized = re.sub(r"\{[^}]+\}", "{x}", p)
        for spec_path in spec_endpoints:
            if re.sub(r"\{[^}]+\}", "{x}", spec_path) == normalized:
                return False
        return True

    stale_in_skills = sorted(
        p for p in (skill_endpoints - spec_endpoints) if _is_real_stale(p)
    )

    now_specced = sorted(UNSPECCED_LIVE_PATHS & spec_endpoints)

    # Apply the same {var} normalization to the "missing" list so variants of
    # path-parameter names don't produce false positives.
    skill_normalized = {
        re.sub(r"\{[^}]+\}", "{x}", p) for p in skill_endpoints
    }
    missing_in_skills = sorted(
        p
        for p in spec_endpoints
        if re.sub(r"\{[^}]+\}", "{x}", p) not in skill_normalized
    )

    enum_report: dict[str, dict[str, Any]] = {}
    for label, steps in TRACKED_ENUMS.items():
        values = walk(spec, steps) or []
        spec_vals = {str(v).lower() for v in values}
        enum_report[label] = {
            "spec": sorted(spec_vals),
            "missing_from_skills": sorted(spec_vals - enum_tokens_in_skills),
            "only_in_skills": sorted(
                (enum_tokens_in_skills & {v.lower() for v in values})
                - spec_vals
            ),
        }

    manifest = {
        p: sorted(endpoint_refs.get(p, [])) for p in sorted(spec_endpoints)
    }

    return {
        "missing_in_skills": missing_in_skills,
        "stale_in_skills": stale_in_skills,
        "now_specced": now_specced,
        "enums": enum_report,
        "manifest": manifest,
    }


def print_report(report: dict[str, Any]) -> bool:
    drift = False

    missing = report["missing_in_skills"]
    stale = report["stale_in_skills"]

    if missing:
        drift = True
        print("\n== Endpoints in spec with no skill coverage ==")
        for p in missing:
            print(f"  [NEW] {p}")

    if stale:
        drift = True
        print("\n== Endpoints referenced in skills but missing from spec ==")
        for p in stale:
            print(f"  [STALE] {p}")

    for p in report["now_specced"]:
        drift = True
        print(f"\n== {p} is now in the spec ==")
        print("  Remove it from UNSPECCED_LIVE_PATHS in this script.")

    for label, data in report["enums"].items():
        if data["missing_from_skills"] or data["only_in_skills"]:
            drift = True
            print(f"\n== Enum drift: {label} ==")
            for v in data["missing_from_skills"]:
                print(f"  [NEW VALUE] {v} (in spec, absent from skills)")
            for v in data["only_in_skills"]:
                print(f"  [STALE VALUE] {v} (in skills, absent from spec)")

    if not drift:
        covered = sum(1 for skills in report["manifest"].values() if skills)
        total = len(report["manifest"])
        print(f"\nAll {total} spec endpoints accounted for "
              f"({covered} referenced in at least one skill). No drift.")
    return drift


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--spec",
        default="https://api.venice.ai/api/v1/swagger.yaml",
        help="URL or local path to the Venice swagger.yaml.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the full diff + manifest as JSON (for CI consumers).",
    )
    args = parser.parse_args()

    spec = load_spec(args.spec)
    report = diff(spec)

    if args.json:
        json.dump(report, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        drift = bool(
            report["missing_in_skills"]
            or report["stale_in_skills"]
            or any(
                e["missing_from_skills"] or e["only_in_skills"]
                for e in report["enums"].values()
            )
        )
    else:
        drift = print_report(report)

    return 1 if drift else 0


if __name__ == "__main__":
    sys.exit(main())
