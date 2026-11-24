import pytest
from pydantic import ValidationError
from callshield.models import AnalyzeRequest
from callshield.agents import analyze


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setenv("CALLSHIELD_LLM_ENABLED", "false")


@pytest.mark.parametrize(
    "text",
    [
        "This is Amazon customer support. Tell me your verification code immediately.",
        "This is bank support. Your account is locked. Transfer money now and tell me your verification code.",
        "Install AnyDesk and send money now.",
        "Please tell me your password.",
        "Buy a gift card and pay now.",
    ],
)
def test_high_risk_scenarios(text):
    result = analyze(AnalyzeRequest(transcript=text))
    assert result["decision"]["risk_level"] == "HIGH"
    assert result["decision"]["should_notify"]
    assert result["decision"]["writeback"] == "suspicious"
    assert len(result["trace"]) == 5
    assert all(f["quote"] in text for f in result["evidence"])


@pytest.mark.parametrize(
    "text",
    [
        "Never share your verification code. The bank will not ask for your password.",
        "\u4e0d\u8981\u63d0\u4f9b\u9a8c\u8bc1\u7801，\u94f6\u884c\u4e0d\u4f1a\u7d22\u53d6\u5bc6\u7801。",
        "My bank appointment is tomorrow. Amazon delivered my package.",
        "\u660e\u5929\u53bb\u94f6\u884c\u529e\u5361，\u4eca\u5929\u4e9a\u9a6c\u900a\u7684\u5feb\u9012\u5230\u4e86。",
    ],
)
def test_benign_or_warning_is_not_fraud(text):
    result = analyze(AnalyzeRequest(transcript=text))
    assert not result["decision"]["should_notify"]
    assert result["decision"]["risk_score"] == 0


def test_asr_failure_is_unknown():
    result = analyze(AnalyzeRequest())
    assert result["decision"]["risk_level"] == "UNKNOWN"
    assert result["decision"]["uncertain"]
    assert result["decision"]["writeback"] == "none"


def test_low_confidence_not_added_to_fraud_score():
    result = analyze(
        AnalyzeRequest(transcript="give me your verification code", asr_confidence=0.2)
    )
    assert result["decision"]["risk_level"] == "MEDIUM"
    assert result["decision"]["risk_score"] <= 0.55


def test_whitelist_cannot_hide_content_risk():
    result = analyze(
        AnalyzeRequest(
            transcript="give me your verification code",
            number_context={"is_whitelisted": True},
        )
    )
    assert result["decision"]["risk_level"] == "HIGH"
    assert result["decision"]["writeback"] == "none"
    assert not result["trace"][2]["output"]["identity_verified"]


def test_missing_confidence_not_reported_as_high_confidence():
    result = analyze(AnalyzeRequest(transcript="hello"))
    assert result["trace"][0]["output"]["confidence_known"] is False


def test_llm_outage_degrades_without_secret_leak(monkeypatch):
    import callshield.agents as agents

    monkeypatch.setenv("CALLSHIELD_LLM_ENABLED", "true")
    monkeypatch.setattr(
        agents,
        "_semantic_findings",
        lambda _: (_ for _ in ()).throw(ValueError("secret-api-key")),
    )
    result = analyze(AnalyzeRequest(transcript="hello"))
    assert result["trace"][1]["output"]["degraded_reason"]
    assert "secret-api-key" not in str(result)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1, 1.1])
def test_invalid_confidence(value):
    with pytest.raises(ValidationError):
        AnalyzeRequest(asr_confidence=value)


def test_secrecy_instruction_is_not_treated_as_benign_negation():
    result = analyze(
        AnalyzeRequest(transcript="Do not hang up, give me your verification code.")
    )
    assert result["decision"]["risk_level"] == "HIGH"
    assert "secrecy" in result["analysis"]["labels"]


def test_semantic_agent_rejects_fabricated_quote(monkeypatch):
    import callshield.agents as agents

    monkeypatch.setenv("OPENAI_API_KEY", "test-only-key")

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": '{"findings":[{"category":"otp_request","quote":"give me your verification code"}]}'
                        }
                    }
                ]
            }

    monkeypatch.setattr(agents.httpx, "post", lambda *a, **k: Response())
    assert agents._semantic_findings("Hello, have a good day.") == []


def test_semantic_null_response_degrades(monkeypatch):
    import callshield.agents as agents

    monkeypatch.setenv("CALLSHIELD_LLM_ENABLED", "true")
    monkeypatch.setattr(
        agents,
        "_semantic_findings",
        lambda _: (_ for _ in ()).throw(TypeError("null response")),
    )
    result = analyze(AnalyzeRequest(transcript="hello"))
    assert result["trace"][1]["output"]["degraded_reason"]


def test_multilingual_remote_access_keeps_english_explanations():
    transcript = "\u8bf7\u5b89\u88c5\u8fdc\u7a0b\u63a7\u5236\u8f6f\u4ef6"
    result = analyze(AnalyzeRequest(transcript=transcript))
    assert result["decision"]["risk_level"] == "HIGH"
    assert result["decision"]["reasons"] == [
        "Request to install remote-access software"
    ]
