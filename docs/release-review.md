# Release code and privacy review

The publication file list was reviewed before the initial public release.

- Source packaging uses an explicit allowlist rather than copying the entire development folder.
- Credentials, `.env`, runtime SQLite files, phone records, recordings, local SDK paths, caches, and signing keys are excluded.
- Sample dialogue and phone numbers are synthetic. Evaluation artifacts contain generated sample speech, not private call recordings.
- The app contains no bundled backend token or model-provider API key. Connection settings are entered at runtime.
- Android cloud-backup and device-transfer rules exclude files, databases, preferences, and app external storage. Backup is also disabled in the manifest.
- The APK is debug-signed. Its public certificate identifies Android Debug; the private signing key is not published.
- The repository commit uses a GitHub no-reply address rather than a personal email address.
- UI text, notifications, API explanations, documentation, and release notes are English. Unicode matching fixtures preserve multilingual coverage.
- Optional semantic inference sends transcripts to the model provider only when configured. This behavior is documented; it is disabled by default.

The credential scan covers common private-key and API-token formats and local user paths. It complements file review; it is not a guarantee against every possible secret format or a production security audit.

Existing validation results are retained for transparency. Additional broad testing was stopped in favor of code review and privacy checks before publication.
