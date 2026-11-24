import io
import wave
import pytest
from httpx import ASGITransport, AsyncClient
from callshield.api import create_app


def wav(seconds=1):
    out = io.BytesIO()
    with wave.open(out, "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(16000)
        stream.writeframes(b"\0\0" * int(seconds * 16000))
    return out.getvalue()


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.delenv("CALLSHIELD_API_TOKEN", raising=False)
    monkeypatch.setenv("CALLSHIELD_LLM_ENABLED", "false")
    monkeypatch.setenv("CALLSHIELD_ASR_ENABLED", "true")
    import callshield.api as api

    monkeypatch.setattr(
        api,
        "transcribe",
        lambda path: (
            "\u6211\u662f\u94f6\u884c\u5ba2\u670d，\u8bf7\u544a\u8bc9\u6211\u9a8c\u8bc1\u7801。",
            0.9,
        ),
    )
    return create_app(tmp_path)


async def test_full_audio_flow_and_idempotency(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        assert (
            await c.post(
                "/v1/calls/init", json={"call_id": "demo", "upload_consent": True}
            )
        ).status_code == 200
        first = await c.post(
            "/v1/calls/demo/segments?index=0",
            files={"audio": ("sample.wav", wav(), "audio/wav")},
        )
        assert first.status_code == 200
        again = await c.post(
            "/v1/calls/demo/segments?index=0",
            files={"audio": ("sample.wav", wav(), "audio/wav")},
        )
        assert again.json()["queued"] is False
        assert (
            await c.post(
                "/v1/calls/demo/segments?index=0",
                files={"audio": ("sample.wav", wav(2), "audio/wav")},
            )
        ).status_code == 409
        result = (await c.get("/v1/calls/demo/alerts")).json()
        assert len(result["alerts"]) == 1
        assert result["alerts"][0]["decision"]["risk_level"] == "HIGH"
        summary = (await c.post("/v1/calls/demo/finalize", json={})).json()["summary"]
        assert summary["decision"]["writeback"] == "suspicious"
        assert (
            await c.post(
                "/v1/calls/demo/segments?index=1", files={"audio": ("x.wav", wav())}
            )
        ).status_code == 409
        assert not list(app.state.store.root.glob("*.wav"))
        assert (await c.delete("/v1/calls/demo")).status_code == 200
        assert (await c.get("/v1/calls/demo/alerts")).status_code == 404


async def test_consent_and_wav_validation(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        await c.post("/v1/calls/init", json={"call_id": "a"})
        assert (
            await c.post(
                "/v1/calls/a/segments?index=0", files={"audio": ("x.wav", wav())}
            )
        ).status_code == 403
        await c.post("/v1/calls/init", json={"call_id": "b", "upload_consent": True})
        assert (
            await c.post(
                "/v1/calls/b/segments?index=0", files={"audio": ("x.wav", b"not audio")}
            )
        ).status_code == 422
        assert (
            await c.post(
                "/v1/calls/b/segments?index=0",
                files={"audio": ("x.wav", b"x" * 512001)},
            )
        ).status_code == 413
        assert (
            await c.post("/v1/calls/init", json={"call_id": "../escape"})
        ).status_code == 422


async def test_auth(app, monkeypatch):
    monkeypatch.setenv("CALLSHIELD_API_TOKEN", "local-test-token")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        assert (await c.get("/health")).status_code == 200
        assert (await c.post("/v1/analyze", json={})).status_code == 401
        assert (
            await c.post(
                "/v1/analyze",
                json={},
                headers={"Authorization": "Bearer local-test-token"},
            )
        ).status_code == 200


async def test_asr_failure_is_not_safe(app, monkeypatch):
    import callshield.api as api

    monkeypatch.setattr(
        api, "transcribe", lambda _: (_ for _ in ()).throw(RuntimeError("failed"))
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        await c.post(
            "/v1/calls/init", json={"call_id": "failed", "upload_consent": True}
        )
        await c.post(
            "/v1/calls/failed/segments?index=0", files={"audio": ("x.wav", wav())}
        )
        summary = (await c.post("/v1/calls/failed/finalize", json={})).json()["summary"]
        assert summary["decision"]["risk_level"] == "UNKNOWN"
        assert summary["failed_segments"] == 1


async def test_finalize_pending_and_user_confirmation(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        await c.post("/v1/calls/init", json={"call_id": "pending"})
        app.state.store.reserve("pending", 0, "digest")
        assert (await c.post("/v1/calls/pending/finalize", json={})).status_code == 409
        assert (await c.delete("/v1/calls/pending")).status_code == 409
        app.state.store.complete("pending", 0, {}, status="failed")
        summary = (
            await c.post("/v1/calls/pending/finalize", json={"confirmed_spam": True})
        ).json()["summary"]
        assert summary["decision"]["writeback"] == "spam"
        assert summary["confirmed_spam"]
