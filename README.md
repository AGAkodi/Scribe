# Scribe

Scribe is a work-in-progress writing companion for the Even G2 simulator. It captures deliberately initiated audio, retrieves a selected Notion project's text and asks for confirmation before a proposed new note is written. The MVP is **not yet ready for production or a hackathon demo**; see [blockers](docs/blockers.md) and [progress](docs/progress.md).

## Local development

Requirements: Node 26 LTS, npm, Python 3.12, and the Even Hub simulator. Install the backend with `python -m venv .venv` and `.venv/Scripts/python -m pip install -r services/api/requirements.txt`. Copy `.env.example` to `.env` and configure it; never commit credentials. Launch from the repository root with `.venv/Scripts/python -m uvicorn scribe.main:app --app-dir services/api --env-file .env --host 127.0.0.1 --port 8000`.

In `apps/g2`, run `npm ci` then `npm run dev`; use the simulator with its URL. Generate a random pairing code (for example, `.venv/Scripts/python -c "import secrets; print(secrets.token_urlsafe(32))"`) and set `SCRIBE_PAIRING_CODE` before starting the API. The code expires ten minutes after first registration and can be used once; rotate it in `.env` and restart to pair again. The resulting session lasts twelve hours and is held in client memory. This is a single-workspace demo flow, not multi-user OAuth.

### Reusable access code (development and judges)

To avoid re-pairing, set `SCRIBE_ACCESS_CODE` (24+ random characters) and `SCRIBE_ACCESS_CODE_EXPIRES` (for example `2026-12-04T23:59:00Z`) in `.env`. Unlike the pairing code, it can be used repeatedly until it expires, and sessions it creates never outlive it. Removing or rotating it and restarting the API revokes all of those sessions. Use it only against the synthetic demo workspace.

For automatic connection in the simulator, create `apps/g2/.env.development.local` (ignored by Git) with `VITE_API_BASE_URL=http://127.0.0.1:8000` and `VITE_DEV_ACCESS_CODE=<the same access code>`. Only `npm run dev` reads that file, and the auto-connect code is removed from production builds, so packaged apps still ask for a code.

The Notion integration expects a projects database and an Ideas database with `Name` (title), `Project` (relation), `Capture ID` (rich text), `Category` (select: `Idea`, `Brainstorm`, `Task`), `AI connection` (text) and `Source references` (text). Share the relevant databases and project pages with the dedicated integration. The implementation pins Notion API `2022-06-28`; validate the workspace schema before real use. Use synthetic demo data.

Actions are bound to the paired session that created them. Actions created before the ownership migration have no owner and are intentionally inaccessible; existing Notion pages are untouched. Generate a new capture if an old pending action cannot be opened.

## Even Hub package

The checked-in `app.json` has an empty network whitelist because the real backend is not deployed yet. Do not pack that manifest directly. Once the HTTPS backend exists, from `apps/g2` set `$env:SCRIBE_API_ORIGIN='https://your-backend.example'` and run `npm run pack`. The script validates the exact non-local HTTPS origin, adds it to the `network` permission, builds the client with the same fixed origin, and invokes the Even Hub CLI with the installed SDK version. Configure backend CORS for the actual app origin separately. A package built with an example origin is not usable for the real backend.

## Verification

Run `.venv/Scripts/python -m pytest tests/test_api.py -q -p no:cacheprovider` and, in `apps/g2`, `npm run build`, `npm run test:lifecycle`, and `npm run test:pack`. These tests use local fixtures; they do not establish physical G2 behavior. See [testing](docs/testing.md).

The G2 client builds upon the MIT-licensed [official ASR starter](https://github.com/even-realities/evenhub-templates), commit `8cb01354f5ee914c5fab97d06e6d13b28eeb5815`. The simulator spike is in `tests/spikes`. Physical hardware has not been tested.
