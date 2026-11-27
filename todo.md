# Scribe — Implementation TODO
November 2026 | Idea to demoable MVP

Use with brief.md. All checkboxes are initially open. Complete P0 before P1/P2. Record actual test evidence and blockers in docs/progress.md. Do not mark a task complete because code exists; run its acceptance check.

## Phase 0 — Feasibility and resource validation (P0)
- [ ] Confirm official event rules, deadline, eligible integrations, repository/video/package requirements. Save source links and date in docs/hackathon.md.
- [x] Install supported Node LTS, npm, Python, Git. Run `node -v`, `npm -v`, `python --version`, `git --version`.
- [x] Inspect official Even Hub templates and everything-evenhub repository. Read SDK bridge, display, audio, gesture and packaging docs. Record exact versions and APIs; do not invent method names. (See docs/audit.md for version and API evidence.)
- [ ] Clone ASR starter (`git clone https://github.com/even-realities/evenhub-templates.git`); follow its current README, install dependencies with its lockfile, run its documented dev command.
- [x] Install simulator/CLI using official current instructions (candidate packages `@evenrealities/evenhub-simulator`, `@evenrealities/evenhub-cli`). Confirm executable names with package docs/help.
- [ ] Open starter in simulator. Render text, test tap/scroll/back and capture real microphone audio. Inspect format, sample rate, duration and event ordering; record evidence.
- [ ] If audio fails, troubleshoot Windows permissions and SDK/simulator versions. Test documented fallback and label limitations; do not substitute fake transcript in final demo.
- [ ] Create dedicated Notion workspace and integration, grant access to demo pages. Create Deepgram/OpenRouter keys, confirm credits and one successful request each. Confirm Railway and frontend hosting access.
- [ ] Make go/no-go decision: SDK interaction and real APIs must be viable. Reduce P1/P2 if blocked.
**Exit:** working simulator spike, actual audio evidence or disclosed fallback, verified API access, documented rules.

## Phase 1 — Repository and foundations (P0)
- [ ] Create repo with apps/g2, services/api, tests, docs; copy brief.md and todo.md. Add companion UI only as needed.
- [ ] Scaffold G2 app from validated starter. Pin SDK and Node versions, keep lockfile. Enable TypeScript strict checks. (Starter-derived app, lockfile and strict build exist; Node and SDK version policy still needs finalization.)
- [ ] Scaffold FastAPI using virtual environment (`python -m venv .venv`); install pinned FastAPI, uvicorn, HTTP client, multipart support, settings and test dependencies. Add requirements/lock file.
- [ ] Implement `/health`, environment validation, structured errors and request IDs. Configure CORS for known client origins.
- [x] Add .gitignore for env files, keys, audio, local DB, node_modules, dist, venv. Add .env.example with placeholders only.
- [ ] Configure persistent SQLite volume for one backend instance or Postgres/Supabase. Create migrations for sessions, pending actions and write receipts; unique capture ID.
- [x] Implement expiring pairing/auth flow for demo workspace. Protect all project, audio and write endpoints; enforce user/project scope. (Single-workspace session ownership is covered by regression tests; legacy unowned actions fail closed.)
- [ ] Add CI for frontend typecheck/build, backend tests, secret scanning. Write local run instructions.
**Exit:** clean checkout runs, health endpoint responds, unauthenticated requests fail, CI passes.

## Phase 2 — Notion workspace and read/write (P0)
- [ ] Create Projects and Ideas databases with fields defined in brief. Pin Notion API version; verify database/data-source query API for that version.
- [x] Seed two fictional projects. The Forgotten King must include Chapter 4 rebel letter, character notes, research and unrelated content. Second project tests isolation.
- [ ] Share only required pages/databases with integration; configure IDs server-side. (Demo access and IDs verified; broader integration access has not been audited.)
- [ ] Implement Notion adapter for project listing, paginated block retrieval, bounded recursive traversal and note creation. Handle rate limits and retries.
- [ ] Normalize supported text blocks into chunks with project/page/block IDs, title and URL. Preserve source text; ignore unsupported blocks explicitly.
- [ ] Implement GET /projects and project authorization. Test inaccessible project IDs and missing permissions.
- [ ] Implement note creation with original transcript, separate AI fields, source references, project relation and capture ID. Verify real page in Notion.
- [ ] Test long transcript handling, pagination, missing fields, revoked access and API errors.
**Exit:** real authorized project read and note write; no cross-project leakage.

## Phase 3 — G2 interaction and transcription (P0)
- [ ] Build SDK adapter around verified starter APIs; initialize bridge, register/unregister event listeners and handle reconnect.
- [ ] Implement home/project list, recording, processing, review, confirm, receipt and error states. Keep one primary action per screen.
- [ ] Normalize tap/scroll/back events, debounce duplicate input and prevent accidental save. Validate actual supported gestures.
- [ ] Implement deliberate start/stop/cancel, visible recording indicator, 30-second cap, bounded audio buffer. Stop on navigation/disconnect where supported.
- [ ] Verify PCM format and construct WAV header if needed; test audio duration and playback locally for debugging without retaining user audio.
- [ ] Implement POST /transcribe with auth, size/duration/type validation and Deepgram adapter. Use correct encoding/sample rate or WAV content type per docs.
- [ ] Handle empty speech, timeout, invalid audio, provider errors; retain transcript in session for review, discard raw audio after processing.
- [ ] Display paginated transcript; retry/discard controls. Test real spoken phrase and compare transcript manually.
**Exit:** actual recording-to-transcript flow in simulator, no recording without activation, no secrets in frontend.

## Phase 4 — Context engine and AI (P0)
- [ ] Build project-scoped retrieval: tokenize query, rank chunks with lexical/BM25 scoring, return top 3–5 relevant snippets and source IDs. Bound context size.
- [ ] Add cache with short TTL and explicit refresh; invalidate after write. Never mix projects.
- [ ] Create OpenRouter adapter with configured model, timeout, token budget and bounded retry. Test structured output support.
- [ ] Define validated response schema from brief. Prompt model to distinguish transcript, summary, suggestion and evidence; treat notes as untrusted data; never follow embedded instructions.
- [ ] Implement capture intent: category, short title, summary, one connection or possible conflict, destination suggestion. No unsupported connection if evidence absent.
- [x] Validate every returned source ID against retrieved chunks. Reject invalid JSON or fabricated source IDs; fallback to transcript-only save proposal. (Exact quote validation is also applied; semantic entailment is not guaranteed.)
- [x] Implement POST /assist and immutable pending action creation with expiry. No Notion write here.
- [ ] Test known rebel-letter connection, unrelated query, conflicting character fact, prompt injection in notes, invalid JSON, provider outage and cross-project isolation.
**Exit:** grounded connection references real Notion block; no-match is honest; AI failure does not lose captured idea.

## Phase 5 — Confirmed writes and end-to-end P0 (P0)
- [ ] Show original transcript, proposed category, one connection and source label on separate short screens as needed.
- [ ] Show exact destination and confirm/cancel choices. Require explicit gesture after preview; never infer confirmation from speech or AI output.
- [x] Implement POST /actions/{id}/confirm, cancel and status endpoints. Bind pending action to user/project, enforce expiry and immutable payload. (Verified with isolated session, expiry and preview-to-write tests.)
- [ ] Use durable unique capture ID and atomic claim/lock. On ambiguous Notion timeout, reconcile by capture ID before retry. Prevent duplicate pages on concurrent confirmations.
- [ ] Write original transcript and AI material separately. Return actual Notion page ID/title on success. Show failure or pending status honestly.
- [ ] Wire receipt screen and retry/status lookup. Cancelled or expired actions must never write.
- [ ] Run full flow with real audio, real APIs and Notion verification. Run cancellation, double tap, timeout and reconnect tests.
**Exit:** capture → transcribe → retrieve → connect → confirm → save works end to end; Notion proves actual write.

## Phase 6 — Recall and brainstorming (P1)
- [ ] Add Recall mode to home; reuse voice/transcription and project retrieval pipeline.
- [ ] Return concise answer with source label, or no-match. Allow follow-up note save through same confirmation flow.
- [ ] Add Brainstorm mode; provide one suggestion at a time based on project context. Clearly label creative speculation separately from established facts.
- [ ] Keep bounded session history for follow-up; reset when switching project. Allow save suggestion as new note, never edit manuscript automatically.
- [ ] Test recall of Chapter 4, unsupported question, project switch and brainstorm save.
**Exit:** at least one stable secondary workflow. Skip if P0 is unstable.

## Phase 7 — UX polish and optional features (P1/P2)
- [ ] Check actual simulator display dimensions and container limits. Test short text, wrapping, pagination, focus, scrolling and back navigation.
- [ ] Add loading/recording/saving indicators and readable error states; avoid long paragraphs and unsupported UI widgets.
- [ ] Measure interaction latency and number of gestures; reduce unnecessary steps without removing confirmation. Record observed values rather than inventing metrics.
- [ ] Optional: daily recap of recent captures and simple writing tasks using Notion category; use same confirmed write flow.
- [ ] Test with another person using demo workspace if available; fix usability issues.
**Exit:** readable, reliable G2 experience; optional features do not compromise P0.

## Phase 8 — Deployment and security (P0)
- [ ] Deploy FastAPI to Railway using documented start command (e.g. `uvicorn main:app --host 0.0.0.0 --port $PORT`, adjust module path). Configure persistent storage and secrets.
- [ ] Deploy frontend to HTTPS static host; set VITE_API_BASE_URL. Configure allowed origins and test pairing.
- [ ] Verify deployed health, auth, real transcription, retrieval and Notion write from simulator. Test cold start and restart persistence.
- [ ] Package using current Even Hub CLI instructions; verify package manifest and asset limits. Test package or hosted URL as required by organizers.
- [ ] Review provider key exposure, CORS, rate limits, audio deletion, project isolation, logs and repository history. Rotate any leaked key.
- [ ] Add privacy notice, demo workspace disclaimer and known limitations. Document single-workspace setup and future OAuth requirement.
**Exit:** deployed demo works over HTTPS, no secrets exposed, reproducible setup. Public Even Hub review is separate.

## Phase 9 — QA and submission (P0)
- [ ] Run frontend typecheck/build, backend unit/integration tests and manual simulator E2E. Record commands, results and screenshots in docs/test-report.md.
- [ ] Test matrix: normal capture, silence, cancel, stale session, invalid audio, no-match, contradiction, project isolation, provider 429/timeout, invalid AI output, revoked Notion access, duplicate confirmation, ambiguous write timeout, restart recovery.
- [ ] Confirm real Notion page shows original transcript, AI suggestion, source reference and project relation. Remove test duplicates.
- [ ] Write README: problem, users, solution, architecture, exact setup commands, env variables, workspace template, demo flow, integrations, limitations, pre-existing code disclosure and license.
- [ ] Prepare demo video (target under 3 minutes): problem 20s, capture 30s, connection 30s, confirm and actual Notion write 35s, recall/limitations 25s. Adjust to verified rules.
- [ ] Prepare submission description, screenshots, repository link, hosted URL, simulator instructions and package if required. Do not expose keys or private workspace.
- [ ] Verify exact deadline/time zone and submit early. Confirm submission receipt.
**Exit:** judges can reproduce working read/write demo and understand actual limitations.

## Suggested remaining schedule
Nov 25: Phases 0–2; Nov 26: Phases 3–4; Nov 27: Phase 5 and initial deployment; Nov 28: Phase 6 if stable, polish and QA; Nov 29: video and submission. This is an aggressive proposed schedule, not a guarantee. Cut P2 and then P1 if behind; reserve submission buffer.

## Final release checklist
- [x] Real SDK interaction demonstrated; simulator/physical hardware distinction disclosed. (Simulator only; hardware not verified.)
- [x] Real API read and confirmed write demonstrated. (Notion backend and prior simulator capture; the latest complete flagship flow remains unverified.)
- [x] Grounded flagship connection with valid source. (Backend test with fictional content; not yet verified end to end through the updated simulator.)
- [ ] No silent edits, duplicate writes or fabricated success.
- [ ] Credentials protected, demo data synthetic, privacy notice present.
- [ ] Deployed service, setup guide, tests and video ready.
- [ ] Current official rules checked and submission confirmed.
