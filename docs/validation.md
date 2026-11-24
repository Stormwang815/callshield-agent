# Validation record

Date: 2026-11-24. This is a prototype validation record, not a production certification.

## Checks

| Check | Recorded result | Scope |
| --- | --- | --- |
| Backend pytest | 27 passed | Rules, uncertainty, fallback behavior, evidence validation, authentication, audio limits, idempotency, finalization, deletion |
| Android unit tests | 10 passed | Local-list precedence, expiry, exact numbers, feedback boundaries |
| Android debug build and lint | Build passed; no lint errors | SDK 36, debug APK; dependency-update warnings remain |
| Synthetic intent evaluation | 9 of 9 expected outcomes | Fixed illustrative cases; not an accuracy benchmark |
| HTTP transcript smoke test | Passed | Running FastAPI server and five-node trace |
| Real local Whisper inference | Passed | Synthetic English speech, tiny CPU int8 |
| WAV-to-API-to-ASR-to-summary | Passed | Real ASR through the ASGI app, temporary audio removed |
| API 35 Emulator install and launch | Passed | Separate package: com.storm.callshield |
| Emulator text-to-backend interaction | Passed | Risk level, reasons, excerpts, and recommendations displayed |
| Emulator incoming-call screening | Passed | Fictional +15555550123: unknown ALLOW, user-confirmed spam REJECT, trusted ALLOW |
| Emulator microphone upload and ASR | Passed | Explicit consent and foreground capture; silent input returned UNKNOWN |

The English publication rebuilds the app and reruns backend tests, Android unit tests, lint, packaging checks, and synthetic evaluation. Screenshot evidence, if included, is captured from the English build. Earlier call-flow and microphone checks were performed before the UI translation; translation alone is not a new real-device test.

The real-ASR example uses system-generated speech rather than a private telephone recording. See `real-asr-smoke.json` and `synthetic-evaluation.json` for scoped artifacts.

## Still unverified

- Real-device, carrier, and vendor-specific two-sided call capture.
- Real-call notification delivery, vibration behavior, battery use, and end-to-end latency.
- Live semantic-model requests and performance on independently labeled fraud data.
- Long-running stability, load, multi-user data isolation, production hosting, and store review.
- Production signing and upgrade compatibility with legacy applications or databases.

No real-world fraud-detection accuracy, energy-reduction percentage, or full-call latency claim is supported by these checks. The heuristic risk score is not a calibrated fraud probability.
