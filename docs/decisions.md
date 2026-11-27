# Decisions

- Use the verified simulator's 16 kHz mono s16le capture path; wrap audio in WAV before submitting it to Deepgram. Raw audio is not deliberately retained server-side.
- Use a bounded lexical retrieval pass for the MVP and require AI source IDs to match retrieved blocks. A failed or unavailable model falls back to a transcript-only proposal.
- Claim actions in SQLite before sending a write. If a Notion request has an uncertain outcome, keep the action in an unknown state rather than retrying automatically. Status lookup checks the Ideas database for the unique capture ID and marks a single matching page saved; a missing or ambiguous match remains unresolved. This path needs real-provider and restart testing.
- Upgrade the starter's vulnerable Vite 5 dependency to Vite 8.3.8. The frontend build and npm audit pass with the resolved dependency tree.
- Bind new actions to the creating session. Existing unowned action records are retained but inaccessible rather than silently transferred to another session.
- Require an exact quote from each referenced source. This prevents fabricated source IDs and quotes but cannot prove that the generated connection is logically supported. Withhold model-proposed contradictions pending stronger verification; do not save uncited AI summaries.
- When the selected model is explicitly free, retry one known free model on rate limit, temporary provider failure or invalid output. Never use a paid fallback automatically.
