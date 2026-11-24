"""Real WAV -> local Whisper -> LangGraph -> summary integration check.

Use synthetic audio only. This is not a real-call or model accuracy evaluation.
"""

import argparse
import asyncio
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
from httpx import ASGITransport, AsyncClient
from callshield.api import create_app


async def run(path):
    with tempfile.TemporaryDirectory(prefix="callshield-real-asr-") as directory:
        app = create_app(Path(directory))
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.post(
                "/v1/calls/init",
                json={"call_id": "synthetic-asr", "upload_consent": True},
            )
            response = await client.post(
                "/v1/calls/synthetic-asr/segments?index=0",
                files={"audio": ("synthetic.wav", path.read_bytes(), "audio/wav")},
            )
            assert response.status_code == 200, response.text
            output = (
                await client.post("/v1/calls/synthetic-asr/finalize", json={})
            ).json()["summary"]
            assert output["failed_segments"] == 0
            assert output["analysis"]["transcript"]
            assert output["decision"]["risk_level"] == "HIGH", output
            assert len(output["trace"]) == 5
            assert not list(Path(directory).glob("*.wav"))
            artifact = {
                "input": "macOS synthetic voice, not a telephone recording",
                "asr_model": "tiny (local CPU int8)",
                "transcript": output["analysis"]["transcript"],
                "decision": output["decision"],
                "node_count": len(output["trace"]),
                "temporary_audio_deleted": True,
                "live_llm_used": False,
            }
            (ROOT / "docs/real-asr-smoke.json").write_text(
                json.dumps(artifact, ensure_ascii=False, indent=2) + "\n"
            )
            print(json.dumps(artifact, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("wav", type=Path)
    asyncio.run(run(parser.parse_args().wav))
