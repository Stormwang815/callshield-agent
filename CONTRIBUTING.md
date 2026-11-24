# Contributing

Use English for code comments, user-facing text, documentation, issues, and pull requests. Keep multilingual detection vocabulary in clearly identified Unicode rules and regression fixtures.

1. Install Python 3.11/3.12 and uv; run `uv sync --frozen`.
2. Make a focused change and add a regression test when behavior changes.
3. Run `uv run pytest -q` and `uv run python scripts/evaluate.py`.
4. For Android changes, run `./gradlew :app:testDebugUnitTest :app:assembleDebug :app:lintDebug` from `android/` with SDK 36 and JDK 17+.
5. Never commit `.env`, recordings, real transcripts, phone lists, databases, local SDK paths, credentials, or signing keys.
6. Describe the problem, implementation, tests, and remaining limitations in the pull request.

Live ASR may download models. Live semantic-model calls are optional, transmit transcript content, and may incur charges. Do not add them to ordinary test runs.

Maintain the distinction between deterministic rules, model-assisted inference, and verified facts. A passing synthetic example does not establish real-world detection accuracy.
