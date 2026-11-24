from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import tempfile
import threading
import time
from collections import defaultdict, deque

from fastapi import (
    BackgroundTasks,
    FastAPI,
    File,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from fastapi.responses import JSONResponse

from .agents import analyze
from .asr import transcribe, validate_wav
from .models import AnalyzeRequest, FinalizeRequest, InitRequest
from .store import Store


class ConsentInit(InitRequest):
    upload_consent: bool = False


def create_app(root: Path | None = None):
    app = FastAPI(title="CallShield Agent", version="0.2.0")
    store = Store(root or Path(os.getenv("CALLSHIELD_DATA_DIR", "./runtime")))
    slots = threading.BoundedSemaphore(2)
    rate: dict[str, deque] = defaultdict(deque)
    app.state.store = store

    @app.middleware("http")
    async def access(request: Request, call_next):
        expected = os.getenv("CALLSHIELD_API_TOKEN", "")
        if request.url.path != "/health":
            token = request.headers.get("authorization", "").removeprefix("Bearer ")
            if expected and not secrets.compare_digest(
                expected.encode(), token.encode()
            ):
                return JSONResponse({"detail": "Invalid access token"}, status_code=401)
            if request.method not in {"GET", "HEAD"}:
                ip = request.client.host if request.client else "unknown"
                now = time.monotonic()
                if len(rate) > 1024:
                    for key in list(rate):
                        if not rate[key] or rate[key][-1] < now - 60:
                            del rate[key]
                bucket = rate[ip]
                while bucket and bucket[0] <= now - 60:
                    bucket.popleft()
                if len(bucket) >= 120:
                    return JSONResponse(
                        {"detail": "Too many requests"}, status_code=429
                    )
                bucket.append(now)
        return await call_next(request)

    def check_id(call_id):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", call_id):
            raise HTTPException(422, "Invalid call ID")
        call = store.call(call_id)
        if call is None:
            raise HTTPException(404, "Call not found")
        return call

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "asr_enabled": os.getenv("CALLSHIELD_ASR_ENABLED", "false").lower()
            == "true",
        }

    @app.post("/v1/analyze")
    def analyze_text(payload: AnalyzeRequest):
        if not slots.acquire(blocking=False):
            raise HTTPException(429, "Analysis is busy; try again later")
        try:
            started = time.monotonic()
            result = analyze(payload)
            result["elapsed_ms"] = round((time.monotonic() - started) * 1000, 2)
            return result
        finally:
            slots.release()

    @app.post("/v1/calls/init")
    def init(payload: ConsentInit):
        if not store.init(
            payload.call_id, payload.number_context.model_dump(), payload.upload_consent
        ):
            raise HTTPException(
                409, "Call ID already exists with different settings; create a new ID"
            )
        return {"ok": True, "call_id": payload.call_id}

    def process(call_id, index, path):
        try:
            with slots:
                call = store.call(call_id)
                if call is None:
                    return
                text, confidence = transcribe(path)
                result = analyze(
                    AnalyzeRequest(
                        transcript=text,
                        asr_confidence=confidence,
                        source_type="microphone",
                        number_context=json.loads(call["context"]),
                    )
                )
            result["call_id"] = call_id
            result["segment_id"] = index
            store.complete(call_id, index, result)
        except Exception:
            result = analyze(AnalyzeRequest(transcript="", source_type="microphone"))
            result["analysis"]["reasons"] = [
                "Speech recognition failed; call safety cannot be assessed"
            ]
            result["call_id"] = call_id
            result["segment_id"] = index
            store.complete(call_id, index, result, status="failed")
        finally:
            path.unlink(missing_ok=True)

    @app.post("/v1/calls/{call_id}/segments")
    async def upload(
        call_id: str,
        background: BackgroundTasks,
        index: int = Query(ge=0, le=359),
        audio: UploadFile = File(...),
    ):
        call = check_id(call_id)
        if not call["consent"]:
            raise HTTPException(403, "Audio upload consent has not been granted")
        if os.getenv("CALLSHIELD_ASR_ENABLED", "false").lower() != "true":
            raise HTTPException(
                503, "ASR is disabled; use the text demo or enable local ASR"
            )
        data = await audio.read(512001)
        await audio.close()
        if len(data) > 512000:
            raise HTTPException(413, "Audio exceeds the 500 KB limit")
        try:
            validate_wav(data)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        digest = hashlib.sha256(data).hexdigest()
        status = store.reserve(call_id, index, digest)
        if status in {"conflict", "closed", "limit"}:
            raise HTTPException(
                409, "Segment conflict, finalized call, or segment limit reached"
            )
        if status == "new":
            try:
                with tempfile.NamedTemporaryFile(
                    dir=store.root, suffix=".wav", delete=False
                ) as stream:
                    stream.write(data)
                    path = Path(stream.name)
                background.add_task(process, call_id, index, path)
            except OSError:
                store.complete(call_id, index, {}, status="failed")
                raise HTTPException(503, "Unable to store the temporary audio file")
        return {
            "ok": True,
            "call_id": call_id,
            "index": index,
            "queued": status == "new",
        }

    @app.get("/v1/calls/{call_id}/alerts")
    def alerts(call_id: str):
        check_id(call_id)
        segments = store.segments(call_id)
        return {
            "ok": True,
            "alerts": [s["result"] for s in segments if s["result"]],
            "pending": sum(s["status"] == "processing" for s in segments),
        }

    @app.post("/v1/calls/{call_id}/finalize")
    def finalize(call_id: str, payload: FinalizeRequest):
        call = check_id(call_id)
        if call["finalized"]:
            return {"ok": True, "summary": json.loads(call["summary"])}
        segments = store.segments(call_id)
        if any(s["status"] == "processing" for s in segments):
            raise HTTPException(
                409, "Segments are still being analyzed; try again later"
            )
        results = [s["result"] for s in segments if s["result"]]
        best = max(
            results,
            key=lambda r: r["decision"]["risk_score"],
            default=analyze(AnalyzeRequest()),
        )
        result = dict(best)
        result["decision"] = dict(best["decision"])
        result["decision"]["writeback"] = (
            "spam" if payload.confirmed_spam else best["decision"]["writeback"]
        )
        result["confirmed_spam"] = payload.confirmed_spam
        result["segment_count"] = len(segments)
        result["failed_segments"] = sum(s["status"] == "failed" for s in segments)
        result["call_id"] = call_id
        if not store.finalize(call_id, result):
            raise HTTPException(409, "Segments are still being analyzed")
        return {"ok": True, "summary": result}

    @app.get("/v1/calls/{call_id}/summary")
    def summary(call_id: str):
        call = check_id(call_id)
        return {
            "ok": True,
            "summary": json.loads(call["summary"]) if call["summary"] else None,
        }

    @app.delete("/v1/calls/{call_id}")
    def delete(call_id: str):
        check_id(call_id)
        if any(s["status"] == "processing" for s in store.segments(call_id)):
            raise HTTPException(
                409, "Wait for analysis to finish before deleting this call"
            )
        store.delete(call_id)
        return {"ok": True}

    return app
