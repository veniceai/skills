#!/usr/bin/env python3
"""Fail when skill content gains a host, wallet address, or shell pipe we have not approved,
or a plugin config starts an MCP server that doesn't match an approved entry.

Agents follow these files literally, and some of them sign USDC payments, so a
changed host or recipient is the edit worth stopping. The allowlists below live
under scripts/, which CODEOWNERS routes to a required reviewer.

Usage:
    python scripts/check_skill_integrity.py --base origin/main   # lines added since base
    python scripts/check_skill_integrity.py --all                # every line in the tree
    python scripts/check_skill_integrity.py --registry           # recorded MCP package hashes vs npm

Exit code 1 when anything is flagged. Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path
from urllib.parse import quote

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
SCHEME_RELATIVE = re.compile(r"[\"'`(=]\s*//((?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,})")
EVM_KEY = re.compile(r"(?<![0-9A-Za-z])0x[0-9a-fA-F]{64}(?![0-9A-Za-z])")
EVM_ADDRESS = re.compile(r"(?<![0-9A-Za-z])0x[0-9a-fA-F]{40}(?![0-9A-Za-z])")
BASE58 = re.compile(r"(?<![0-9A-Za-z])[1-9A-HJ-NP-Za-km-z]{32,44}(?![0-9A-Za-z])")
BASE58_SECRET = re.compile(r"(?<![0-9A-Za-z])[1-9A-HJ-NP-Za-km-z]{80,90}(?![0-9A-Za-z])")
PIPE_TO_SHELL = re.compile(
    r"(curl|wget)\b[^\n]*\|\s*(sudo\s+)?((ba|z|da)?sh|python[0-9.]*|node|perl|ruby)\b"
    r"|(ba|z)?sh\s+<\(\s*(curl|wget)"
    r"|\b(iex|Invoke-Expression)\b",
    re.IGNORECASE,
)


# A plugin install starts its MCP servers with the user's Venice key in their
# environment, so each one has to match an approved entry field for field.
# Values are the key setting each config may pass as VENICE_API_KEY.
PLUGIN_MCP_CONFIGS = {
    ".claude-plugin/plugin.json": "${user_config.venice_api_key}",
    ".mcp.json": "${user_config.venice_api_key}",
    ".cursor-plugin/plugin.json": "${VENICE_API_KEY}",
    "mcp.json": "${VENICE_API_KEY}",
}
PLUGIN_MARKETPLACES = {
    ".claude-plugin/marketplace.json": "${user_config.venice_api_key}",
    ".cursor-plugin/marketplace.json": "${VENICE_API_KEY}",
}
# Each version maps to the npm dist.integrity of its tarball, so pinning a new
# version means a code owner records the exact artifact it resolves to.
MCP_PACKAGES = {
    "@veniceai/mcp-server": {
        "0.3.0": "sha512-zF/41cFgwAJFRrR45Yh5KRkEFMQmdqtoJ08ZBenbgqfhZ2de+m21kcfxlSKUa3IA4sTtGt0jdm4PSnePbVjziQ==",
    },
}
NPX_PREFIX = ["-y", "--ignore-scripts"]
OPTIONAL_MCP_ENV = {"VENICE_DISABLE_NSFW": "1"}
STDIO_MCP_FIELDS = {"type", "command", "args", "env"}
REMOTE_MCP_FIELDS = {"type", "url", "headers"}
REMOTE_MCP_TYPES = {"http", "sse", "streamable-http"}
PACKAGE_SPEC = re.compile(r"(@[a-z0-9][a-z0-9._-]*/[a-z0-9][a-z0-9._-]*|[a-z0-9][a-z0-9._-]*)@([0-9]+\.[0-9]+\.[0-9]+)")


def looks_like_base58_address(token: str) -> bool:
    return any(c.isdigit() for c in token) and any(c.isupper() for c in token) and any(c.islower() for c in token)


def url_findings(line: str) -> list[str]:
    found = []
    for match in URL_TOKEN.finditer(line):
        url = match.group(0).rstrip(".;:!?*")
        rest = url.split(":", 1)[1]
        if rest == "//":
            if line[match.end():match.end() + 1] in ("{", "<", "["):
                found.append(f"templated URL host: {line[match.start():match.end() + 1]}…")
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
    for host in SCHEME_RELATIVE.findall(line):
        if host.lower().rstrip(".") not in ALLOWED_HOSTS:
            found.append(f"scheme-relative URL host: {host}")
    return found


def findings_for(line: str) -> list[str]:
    found = url_findings(line)
    for key in EVM_KEY.findall(line):
        found.append(f"possible private key: {key[:10]}…")
    for key in BASE58_SECRET.findall(line):
        found.append(f"possible base58 private key: {key[:10]}…")
    for address in EVM_ADDRESS.findall(line):
        if address.lower() not in KNOWN_ADDRESSES:
            found.append(f"unknown EVM address: {address}")
    for token in BASE58.findall(line):
        if looks_like_base58_address(token) and token not in KNOWN_ADDRESSES:
            found.append(f"unknown base58 address: {token}")
    if PIPE_TO_SHELL.search(line):
        found.append("pipe-to-shell pattern")
    return found


def pinned_package(spec: object) -> bool:
    match = PACKAGE_SPEC.fullmatch(spec) if isinstance(spec, str) else None
    return bool(match) and match.group(2) in MCP_PACKAGES.get(match.group(1), {})


def remote_mcp_findings(name: str, server: dict) -> list[str]:
    found = [f"MCP server {name}: unexpected field {key}" for key in sorted(set(server) - REMOTE_MCP_FIELDS)]
    if server.get("type", "http") not in REMOTE_MCP_TYPES:
        found.append(f"MCP server {name}: unexpected type {server.get('type')!r}")
    url = server.get("url")
    if not isinstance(url, str) or not url.startswith("https://"):
        found.append(f"MCP server {name}: URL must use https: {url}")
    else:
        found += [f"MCP server {name}: {finding}" for finding in url_findings(url)]
    headers = server.get("headers", {})
    if not isinstance(headers, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in headers.items()):
        found.append(f"MCP server {name}: headers must map names to strings")
    return found


def stdio_mcp_findings(name: str, server: dict, key_ref: str) -> list[str]:
    found = [f"MCP server {name}: unexpected field {key}" for key in sorted(set(server) - STDIO_MCP_FIELDS)]
    if server.get("type", "stdio") != "stdio":
        found.append(f"MCP server {name}: unexpected type {server.get('type')!r}")
    if server.get("command") != "npx":
        found.append(f"MCP server {name}: only npx may start a server, not {server.get('command')!r}")
    args = server.get("args")
    if not (isinstance(args, list) and len(args) == 3 and args[:2] == NPX_PREFIX and pinned_package(args[2])):
        found.append(f"MCP server {name}: args must be exactly -y --ignore-scripts and a recorded package version, not {args}")
    env = server.get("env")
    if not (
        isinstance(env, dict)
        and env.get("VENICE_API_KEY") == key_ref
        and all(OPTIONAL_MCP_ENV.get(key) == value for key, value in env.items() if key != "VENICE_API_KEY")
    ):
        found.append(f"MCP server {name}: env must be exactly VENICE_API_KEY={key_ref}, optionally with VENICE_DISABLE_NSFW=1")
    return found


def mcp_server_findings(name: str, server: object, key_ref: str) -> list[str]:
    if not isinstance(server, dict):
        return [f"MCP server {name}: not an object"]
    if "url" in server:
        return remote_mcp_findings(name, server)
    return stdio_mcp_findings(name, server, key_ref)


def read_json_object(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def servers_findings(rel: str, servers: object, key_ref: str, where: str = "") -> list[tuple[str, str]]:
    if isinstance(servers, str) and servers.removeprefix("./") in PLUGIN_MCP_CONFIGS:
        return []
    if not isinstance(servers, dict):
        return [(rel, f"{where}mcpServers must be inline or point to a checked config file")]
    return [(rel, where + finding) for name, server in servers.items() for finding in mcp_server_findings(name, server, key_ref)]


def plugin_mcp_findings(root: Path) -> list[tuple[str, str]]:
    found = []
    for rel, key_ref in PLUGIN_MCP_CONFIGS.items():
        if (root / rel).is_file():
            config = read_json_object(root / rel)
            if config is None:
                found.append((rel, "not a JSON object"))
            else:
                found += servers_findings(rel, config.get("mcpServers", {}), key_ref)
    for rel, key_ref in PLUGIN_MARKETPLACES.items():
        if (root / rel).is_file():
            marketplace = read_json_object(root / rel)
            if marketplace is None:
                found.append((rel, "not a JSON object"))
                continue
            for entry in marketplace.get("plugins", []):
                if isinstance(entry, dict) and "mcpServers" in entry:
                    found += servers_findings(rel, entry["mcpServers"], key_ref, f"plugin {entry.get('name')}: ")
    return found


def fetch_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.load(response)


def registry_findings(fetch=fetch_json) -> list[tuple[str, str]]:
    found = []
    for name, versions in MCP_PACKAGES.items():
        for version, recorded in versions.items():
            url = f"https://registry.npmjs.org/{quote(name, safe='@')}/{version}"
            try:
                published = fetch(url).get("dist", {}).get("integrity")
            except Exception as error:  # any failure to confirm the hash fails closed
                found.append((SELF, f"couldn't read {name}@{version} from the npm registry: {error}"))
                continue
            if published != recorded:
                found.append((SELF, f"npm serves {name}@{version} with integrity {published}, not the recorded {recorded}"))
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
    mode.add_argument("--registry", action="store_true", help="check each recorded MCP package hash against npm")
    args = parser.parse_args()

    if args.registry:
        problems = [(path, 1, finding) for path, finding in registry_findings()]
    else:
        lines = all_lines() if args.all else added_lines(args.base)
        problems = [
            (path, lineno, finding)
            for path, lineno, line in lines
            if path not in UNSCANNED
            for finding in findings_for(line)
        ]
        problems += [(path, 1, finding) for path, finding in plugin_mcp_findings(Path("."))]
    for path, lineno, finding in problems:
        print(f"::error file={path},line={lineno}::{finding}")
    if problems:
        print(
            f"\n{len(problems)} finding(s). If a new host, address or MCP package is intended, add it to the "
            f"allowlist in {SELF} in the same PR so a code owner reviews it.",
            file=sys.stderr,
        )
        return 1
    print("Skill integrity check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
