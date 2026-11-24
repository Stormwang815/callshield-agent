# CallShield Agent

**Explainable call-risk analysis with Android screening and a five-node LangGraph pipeline.**

CallShield combines local phone-number screening with user-started microphone sampling, local speech recognition, evidence-based risk analysis, and temporary suspicious-number feedback.

> Research prototype for personal testing and trusted deployments. It does not guarantee capture of both sides of a phone call or protection against fraud.

[Getting started](#quick-start) · [Architecture](docs/architecture.md) · [Validation](docs/validation.md) · [Security](SECURITY.md) · [Releases](https://github.com/Stormwang815/callshield-agent/releases)

## Features

- **Local-first screening:** exact international-number matching in Room, trusted-number precedence, user-confirmed spam blocking, and expiring suspicious-number flags.
- **Bounded screening:** local database access only, with a 1.5-second allow fallback. No backend or model calls on the screening path.
- **Consent-based capture:** user-started microphone foreground service, a visible notification, approximately 10-second segments, and a 60-second session limit.
- **Local ASR:** optional faster-whisper integration, a reused model instance, format/size/duration limits, and temporary audio cleanup.
- **Explainable analysis:** transcript-quality checks, scam-intent detection, number context, risk fusion, and protective recommendations, with evidence and execution traces.
- **Conservative feedback:** automatic suspicious flags expire after 14 days; permanent spam blocking requires user confirmation. Text demos do not update real-number lists.
- **Honest uncertainty:** empty or failed transcription produces `UNKNOWN`, not a claim that the call is safe.

The application UI, API explanations, notifications, documentation, and release material are in English. Multilingual matching remains supported through Unicode-based rules and regression fixtures. Quoted evidence preserves the language of the input.

## Quick start

Requirements: Python 3.11 or 3.12 and [uv](https://docs.astral.sh/uv/getting-started/installation/).

```bash
git clone https://github.com/Stormwang815/callshield-agent.git
cd callshield-agent
uv sync --frozen
cp .env.example .env
uv run --env-file .env uvicorn callshield.api:create_app --factory --app-dir backend --host 127.0.0.1 --port 8011
```

Verify the backend:

```bash
curl http://127.0.0.1:8011/health
curl http://127.0.0.1:8011/v1/analyze \
  -H 'Content-Type: application/json' \
  -d '{"transcript":"This is bank support. Transfer money now and tell me your verification code.","source_type":"text_demo"}'
```

The default rule-based text demo requires no API key or paid service. A high-risk result contains a risk level, supporting transcript excerpts, recommendations, and five node traces. The score is a heuristic, not a calibrated probability of fraud.

### Enable local speech recognition

```bash
uv sync --frozen --extra asr
```

Set `CALLSHIELD_ASR_ENABLED=true` in `.env`, then restart using `uv run --extra asr --env-file .env ...`. Keeping `--extra asr` in subsequent uv commands retains the optional ASR dependencies.

The default model is multilingual `base`; first use may download model files. `tiny` was used for the documented synthetic-audio smoke test. CPU inference is serialized and the model is reused. The quality indicator derived from Whisper log probabilities is not a calibrated transcription-accuracy score.

Audio uploads return HTTP 503 when ASR is disabled. This is an explicit configuration state, not a successful audio-analysis result.

### Optional semantic model

Set `CALLSHIELD_LLM_ENABLED=true`, `OPENAI_API_KEY`, and `CALLSHIELD_LLM_MODEL`. Only the Scam Intent node calls the external model. Transcript content is sent to the provider and usage may incur fees. The response must match a fixed schema and cite excerpts present in the transcript. On supported provider errors, the node falls back to rules.

The default pipeline consists of deterministic specialist nodes, **not five independently reasoning LLMs**. Live semantic-model quality has not been validated.

## Android app

Download the debug APK from [GitHub Releases](https://github.com/Stormwang815/callshield-agent/releases), or build it with Android SDK 36 and JDK 17+.

Create `android/local.properties` with your own SDK path:

```properties
sdk.dir=/path/to/your/Android/sdk
```

```bash
cd android
./gradlew :app:testDebugUnitTest :app:assembleDebug :app:lintDebug
```

Output: `android/app/build/outputs/apk/debug/app-debug.apk`.

1. Open the app and select **Enable call screening**.
2. Enter a full international number. Trust it, confirm it as spam, or inspect/remove its local flags.
3. Set the backend URL. Android Emulator uses `http://10.0.2.2:8011`; remote backends require HTTPS.
4. Run the text demo first. It displays results without modifying number lists.
5. For microphone analysis, enable backend ASR, grant permissions, and explicitly agree to recording and uploading. Stop using the notification or the Stop button.
6. View the latest result, or delete the latest backend record. Local number flags are managed separately.

Package ID: `com.storm.callshield`. Minimum Android version: 8.0; call screening is primarily targeted at Android 10+. Android 8/9 cannot use the newer silence-call response. The app uses a separate package and database from the legacy prototype; it does not migrate old data.

### Important audio limitation

An ordinary Android app cannot guarantee capture of both sides of a call. This app uses the regular microphone, requests no privileged call-audio permission, does not force speakerphone mode, and never starts recording from a boot receiver. Capture may fail, be silent, or contain only nearby speech.

Sampling, upload, and analysis currently run sequentially. Network and inference delays create sampling gaps; this is a near-real-time prototype rather than continuous two-way audio streaming. With optional phone-state permission, a user-started session stops when a call ends after an off-hook state has been observed.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Service and ASR configuration status |
| POST | `/v1/analyze` | Analyze a transcript without persistence |
| POST | `/v1/calls/init` | Create a call ID, number context, and upload-consent record |
| POST | `/v1/calls/{id}/segments?index=0` | Upload a mono 16 kHz, 16-bit PCM WAV segment |
| GET | `/v1/calls/{id}/alerts` | Read analyzed segments and pending count |
| POST | `/v1/calls/{id}/finalize` | Finalize after all segments finish |
| GET | `/v1/calls/{id}/summary` | Read the final summary |
| DELETE | `/v1/calls/{id}` | Delete the call's stored transcripts and results |

Segment indices are 0–359. Uploads accept 0.2–15 seconds of audio and at most 500 KB. Repeated identical segments are idempotent; conflicting content at the same index is rejected. Finalization and deletion return HTTP 409 while analysis is pending.

Set `CALLSHIELD_API_TOKEN` for a trusted deployment and send `Authorization: Bearer <token>`. This shared token is not a multi-user authorization system. Keep **one worker and one instance**; see [Security](SECURITY.md) before exposing the service.

## Development and validation

```bash
uv run pytest -q
uv run python scripts/evaluate.py
# Optional real local-ASR smoke test using synthetic speech:
CALLSHIELD_ASR_ENABLED=true CALLSHIELD_ASR_MODEL=tiny \
  uv run --extra asr python scripts/verify_asr.py /path/to/synthetic.wav
python3 scripts/build_release.py
```

Current validation includes 27 backend tests, 10 Android unit tests, Android lint/build checks, synthetic intent cases, local Whisper inference, and Android Emulator interaction. The English release reruns the applicable checks; detailed scope is in [Validation](docs/validation.md).

Synthetic results do not establish real-world accuracy. Real-device audio capture, end-to-end latency, battery use, live LLM behavior, production security, and store approval remain unverified.

## Repository layout

```text
android/              Java app, Room lists, call screening, microphone capture
backend/callshield/   FastAPI, SQLite, local ASR, five-node LangGraph pipeline
backend/tests/        Isolated backend regression tests
scripts/              Evaluation, real-ASR smoke test, safe source packaging
docs/                 Architecture, validation, and synthetic evaluation artifacts
releases/             APK usage notes and checksum; binaries are release assets
```

The source packager uses an explicit allowlist and excludes credentials, runtime databases, recordings, local SDK paths, build caches, and APKs. APKs are published as separate release assets, with a SHA-256 checksum. They are debug-signed test builds, not store-ready production releases.

## Platform references

- [Android CallScreeningService](https://developer.android.com/reference/android/telecom/CallScreeningService): incoming calls require a response within five seconds.
- [Android sharing audio input](https://developer.android.com/media/platform/sharing-audio-input): ordinary apps face call-audio capture restrictions.

## CI configuration

A ready-to-use workflow template is included at `docs/ci-workflow.example.yml`. The publishing login does not have the GitHub workflow permission, so Actions is not enabled automatically. Copy the template to `.github/workflows/checks.yml` using an appropriately authorized login to activate it.

## License

[Apache License 2.0](LICENSE). Third-party dependencies retain their own licenses; see [Third-party notices](THIRD_PARTY_NOTICES.md).
