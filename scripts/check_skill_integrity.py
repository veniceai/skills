#!/usr/bin/env python3
"""Fail when skill content gains a host, wallet address, or shell pipe we have not approved.

Agents follow these files literally, and some of them sign USDC payments, so a
changed host or recipient is the edit worth stopping. The allowlists below live
under scripts/, which CODEOWNERS routes to a required reviewer.

Usage:
    python scripts/check_skill_integrity.py --base origin/main   # lines added since base
    python scripts/check_skill_integrity.py --all                # every line in the tree

Exit code 1 when anything is flagged. Stdlib only.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

SCANNED_PATHS = ["skills", "scripts", "template", "AGENTS.md", "skills.json"]
SELF = "scripts/check_skill_integrity.py"
UNSCANNED = {SELF, "scripts/test_check_skill_integrity.py"}

ALLOWED_HOSTS = {
    "api.venice.ai",
    "docs.venice.ai",
    "venice.ai",
    "cdn.venice.ai",
    "example.com",
    "huggingface.co",
    "api.openai.com",
    "www.youtube.com",
    "json-schema.org",
}

KNOWN_ADDRESSES = {
    "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",  # USDC on Base
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC on Solana
    "5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp",  # Solana mainnet genesis (CAIP-2 reference)
}

# Take the whole token after the scheme and parse it ourselves. URL parsers and
# curl resolve userinfo, percent-encoding, backslashes and missing slashes in
# ways a reader of the skill would not, so anything but a plain host fails.
URL_TOKEN = re.compile(r"\bhttps?:[^\s\"'`<>()\[\]{}|,]*", re.IGNORECASE)
PLAIN_AUTHORITY = re.compile(r"[A-Za-z0-9.-]+(:[0-9]{1,5})?")
FETCH_COMMAND = re.compile(r"\b(curl|wget)\b", re.IGNORECASE)
BARE_HOST = re.compile(r"(?<![\w@./:%-])((?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,})(?::[0-9]{1,5})?/")
EVM_KEY = re.compile(r"(?<![0-9A-Za-z])0x[0-9a-fA-F]{64}(?![0-9A-Za-z])")
EVM_ADDRESS = re.compile(r"(?<![0-9A-Za-z])0x[0-9a-fA-F]{40}(?![0-9A-Za-z])")
BASE58 = re.compile(r"(?<![0-9A-Za-z])[1-9A-HJ-NP-Za-km-z]{32,44}(?![0-9A-Za-z])")
PIPE_TO_SHELL = re.compile(
    r"(curl|wget)\b[^\n]*\|\s*(sudo\s+)?(ba|z|da)?sh\b"
    r"|(ba|z)?sh\s+<\(\s*(curl|wget)"
    r"|\b(iex|Invoke-Expression)\b",
    re.IGNORECASE,
)


def looks_like_base58_address(token: str) -> bool:
    return any(c.isdigit() for c in token) and any(c.isupper() for c in token) and any(c.islower() for c in token)


def url_findings(line: str) -> list[str]:
    found = []
    for match in URL_TOKEN.finditer(line):
        url = match.group(0).rstrip(".;:!?*")
        rest = url.split(":", 1)[1]
        if rest == "//":
            continue
        if "\\" in url:
            found.append(f"backslash in URL: {url}")
            continue
        if not rest.startswith("//") or rest.startswith("///"):
            found.append(f"malformed URL: {url}")
            continue
        authority = re.split(r"[/?#]", rest[2:], maxsplit=1)[0]
        if "@" in authority:
            found.append(f"credentials in URL authority: {url}")
        elif "%" in authority:
            found.append(f"percent-encoded URL authority: {url}")
        elif not PLAIN_AUTHORITY.fullmatch(authority):
            found.append(f"unparsable URL host: {url}")
        else:
            host = authority.split(":", 1)[0].lower().rstrip(".")
            if host not in ALLOWED_HOSTS:
                found.append(f"host not in allowlist: {host}")
    if FETCH_COMMAND.search(line):
        for host in BARE_HOST.findall(line):
            if host.lower().rstrip(".") not in ALLOWED_HOSTS:
                found.append(f"scheme-less host in {FETCH_COMMAND.search(line).group(1)} command: {host}")
    return found


def findings_for(line: str) -> list[str]:
    found = url_findings(line)
    for key in EVM_KEY.findall(line):
        found.append(f"possible private key: {key[:10]}…")
    for address in EVM_ADDRESS.findall(line):
        if address.lower() not in KNOWN_ADDRESSES:
            found.append(f"unknown EVM address: {address}")
    for token in BASE58.findall(line):
        if looks_like_base58_address(token) and token not in KNOWN_ADDRESSES:
            found.append(f"unknown base58 address: {token}")
    if PIPE_TO_SHELL.search(line):
        found.append("pipe-to-shell pattern")
    return found


def added_lines(base: str):
    diff = subprocess.run(
        ["git", "diff", "--unified=0", "--no-color", f"{base}...HEAD", "--", *SCANNED_PATHS],
        check=True, capture_output=True, text=True,
    ).stdout
    path, lineno = None, 0
    for raw in diff.splitlines():
        if raw.startswith("+++ "):
            path = raw[6:] if raw.startswith("+++ b/") else None
        elif raw.startswith("@@"):
            lineno = int(re.search(r"\+(\d+)", raw).group(1))
        elif raw.startswith("+") and path:
            yield path, lineno, raw[1:]
            lineno += 1


def all_lines():
    for root in SCANNED_PATHS:
        for file in [Path(root)] if Path(root).is_file() else sorted(Path(root).rglob("*")):
            if not file.is_file():
                continue
            try:
                text = file.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for lineno, line in enumerate(text.splitlines(), 1):
                yield str(file), lineno, line


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--base", help="git ref to diff against; only added lines are checked")
    mode.add_argument("--all", action="store_true", help="check every line in the scanned paths")
    args = parser.parse_args()

    lines = all_lines() if args.all else added_lines(args.base)
    problems = [
        (path, lineno, finding)
        for path, lineno, line in lines
        if path not in UNSCANNED
        for finding in findings_for(line)
    ]
    for path, lineno, finding in problems:
        print(f"::error file={path},line={lineno}::{finding}")
    if problems:
        print(
            f"\n{len(problems)} finding(s). If a new host or address is intended, add it to the "
            f"allowlist in {SELF} in the same PR so a code owner reviews it.",
            file=sys.stderr,
        )
        return 1
    print("Skill integrity check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
