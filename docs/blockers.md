# Blockers and remaining work

## Account-dependent verification

- The [Scribe Demo](https://app.notion.com/p/4239a95d2c4e81c5a05cf34bad4377a7) databases and fictional projects are created. The backend token and database IDs are configured; real project retrieval and a confirmed synthetic write were verified with the pinned Notion API version. Full end-to-end flow, AI metadata, and failure/restart scenarios remain to be verified.
- Deepgram and OpenRouter keys are configured and authenticated. A user-driven live simulator capture reached transcript review. The selected free Particle model produced source-referenced results in three repeat backend checks and one real synthetic demo save; full live simulator verification and longer-term free-model availability remain open.
- Verify the event's submission requirements and deadline directly with the organizer listing. Current third-party reporting is provisional; see `hackathon.md`.
- Configure a persistent Railway volume and deployment credentials only after the production safety gaps below are resolved and provider settings are available. Railway account access itself was confirmed.

## Implementation gaps

The audit fixes now include session-bound actions, lifecycle shutdown, exact source-quote checks, preview-aligned writes, mode-specific recall/brainstorm and an origin-specific package generator. Remaining work includes physical-device and latest simulator end-to-end verification, a real deployed HTTPS origin and package test, production security review and distributed rate limiting, request logging review, semantic grounding beyond exact-quote checks, and real-provider failure/restart reconciliation. Free-model rate limits can still prevent an answer. No deployment or submission has been made.
