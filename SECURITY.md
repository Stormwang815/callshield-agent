# Security and privacy

This is a single-instance research prototype for local use or a trusted deployment. Do not expose it as an anonymous public service.

## Reporting issues

Use GitHub's private vulnerability reporting feature if enabled. Otherwise, open a minimal issue requesting a private contact channel without disclosing exploit details, credentials, recordings, phone numbers, or transcripts. Do not publish personal call data in issues or pull requests.

## Deployment boundaries

- Default to loopback access. Remote use requires HTTPS and a strong `CALLSHIELD_API_TOKEN`.
- The token is shared by the deployment. It does not provide user accounts, tenant isolation, or per-call authorization.
- Use one worker and one instance. Inference limits, rate limits, and processing-state recovery are not distributed.
- Recordings require explicit user action and consent. Follow applicable recording and data-handling requirements for your situation.
- Local phone numbers remain on the device; transcripts and results are stored in the backend SQLite database.
- Temporary audio is deleted after processing. A crash may leave temporary audio; configure cleanup and retention for the runtime directory.
- The delete endpoint removes logical records, not forensic traces from SQLite journals, backups, or storage media.
- Optional LLM inference sends transcripts to an external provider. Local-ASR operation alone does not imply all features are offline.
- Transcript content is untrusted. Evidence checks and a constrained output schema reduce some errors but do not solve prompt injection, semantic mistakes, or adversarial dialogue.
- Automatic suspicion does not permanently block a number. Permanent spam classification requires user confirmation.

Debug APKs are for evaluation. They are not production-signed, audited, or approved for app-store distribution.
