"""Small synthetic regression evaluation, not a real-world accuracy benchmark."""

import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
from callshield.agents import analyze
from callshield.models import AnalyzeRequest

CASES = [
    (
        "Bank impersonation and code request",
        "\u6211\u662f\u94f6\u884c\u5ba2\u670d，\u8bf7\u544a\u8bc9\u6211\u9a8c\u8bc1\u7801。",
        "HIGH",
    ),
    (
        "Support impersonation and code request",
        "This is Amazon customer support. Please read your verification code.",
        "HIGH",
    ),
    ("Remote access", "Install AnyDesk now.", "HIGH"),
    (
        "Urgent payment",
        "\u8bf7\u7acb\u5373\u8f6c\u8d26\u5230\u6307\u5b9a\u8d26\u6237。",
        "HIGH",
    ),
    ("Credential request", "Please tell me your password.", "HIGH"),
    ("Anti-fraud warning", "Never share your verification code.", "LOW"),
    ("Benign mention of a bank", "I have a bank appointment tomorrow.", "LOW"),
    (
        "Multilingual anti-fraud warning",
        "\u4e0d\u8981\u63d0\u4f9b\u9a8c\u8bc1\u7801，\u94f6\u884c\u4e0d\u4f1a\u7d22\u53d6\u5bc6\u7801。",
        "LOW",
    ),
    ("No speech", "", "UNKNOWN"),
]
results = []
for name, text, expected in CASES:
    start = time.perf_counter()
    output = analyze(AnalyzeRequest(transcript=text))
    elapsed = (time.perf_counter() - start) * 1000
    actual = output["decision"]["risk_level"]
    results.append(
        {
            "case": name,
            "expected": expected,
            "actual": actual,
            "passed": actual == expected,
            "rule_graph_ms": round(elapsed, 3),
        }
    )
artifact = {
    "scope": "Synthetic cases, rules only; excludes audio, ASR, network and device latency.",
    "cases": results,
    "passed": sum(x["passed"] for x in results),
    "total": len(results),
}
(ROOT / "docs/synthetic-evaluation.json").write_text(
    json.dumps(artifact, ensure_ascii=False, indent=2) + "\n"
)
print(json.dumps(artifact, ensure_ascii=False, indent=2))
raise SystemExit(0 if all(x["passed"] for x in results) else 1)
