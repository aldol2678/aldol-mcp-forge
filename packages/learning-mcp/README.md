# ALDOL Learning MCP v0.1.0

Source-first, single-owner learning MCP with **8 working tools** and SQLite storage. Built as an isolated package in ALDOL MCP Forge. Python 3.11+.

## Tools

| Tool | Purpose |
| --- | --- |
| `create_course(title, subject, goal)` | Create a course |
| `ingest_material(course_id, title, content)` | Save up to 30,000 characters of plain text |
| `generate_lesson(course_id, max_excerpts=3)` | Return source-attributed excerpts |
| `generate_quiz(course_id, count=5)` | Retrieve extracted Q/A prompts without answers |
| `submit_answer(question_id, answer)` | Record practice with exact-match flag and next review |
| `analyze_weakness(course_id)` | Detect responses needing manual review |
| `get_due_reviews(course_id, limit=20)` | Return unseen and due cards |
| `get_learning_progress(course_id)` | Count attempts, exact matches and due prompts |

**Important:** Despite their names, `generate_lesson` and `generate_quiz` are source-retrieval, **not LLM content generation**. Use `Q: ...` / `A: ...` (or `질문:` / `정답:`) on consecutive lines to extract up to 20 prompts per imported material. Imported answers are always **UNVERIFIED**; a text mismatch becomes `NEEDS_REVIEW`, not a proof of incorrectness. The included simple interval scheduler is **NOT FSRS**.

## Tests

```sh
cd packages/learning-mcp
python -m unittest discover -s tests -v
```

Core tests do not require the external MCP library. MCP SDK transport integration and real client connectivity must be tested separately.

## Running locally

```sh
python -m venv .venv
.venv/bin/pip install -r requirements.txt
LEARNING_DB_PATH="$PWD/data/learning.sqlite3" .venv/bin/python server.py
```

To run over Streamable HTTP, use a verified HTTPS reverse proxy with durable private storage:

```sh
LEARNING_OWNER_TOKEN='<random-secret-of-32-or-more-characters>' \
LEARNING_DB_PATH='/persistent-private-volume/learning.sqlite3' \
PORT=8000 python server.py --http
```

All HTTP requests require `Authorization: Bearer <owner secret>`; the server refuses browser Origin requests. **Do not deploy an unauthenticated public endpoint.** This is single-owner storage without per-user tenancy. The token must be injected via a secrets manager, never committed or included in the MCP manifest. A local SQLite file is created with owner-only permissions on POSIX; a private durable volume and backup are still needed.

## Mobile / ChatGPT limitations

- Remote transport code is present but **no public deployment or app registration was performed**.
- This version does **not** implement OAuth 2.1 + PKCE discovery or any provider login. A static bearer token is not a completed ChatGPT custom MCP Android integration.
- The Android ChatGPT app has **not** been tested. Do not claim mobile compatibility without a real authenticated Android tool call and persistence readback.
- A mobile web UI is **not included**.

## Explicit out-of-scope items

No PDF/URL fetching; no network-based knowledge claims; no AI tutoring or semantic grading; no FSRS; no import of existing Induck Campus question banks; no multi-user storage; no release deployment. Raw text is untrusted data and may contain misleading instructions. Validate rights and answer keys before production reuse.

**Write-call caveat:** `submit_answer` creates a new attempt on each call. Do not automatically retry write calls until idempotency keys are implemented. This source is a prototype for review, not an approved production service.

## Next gates

1. Review and verify original Induck Campus records, content rights, and question/answer quality.
2. Add idempotency and an audited OAuth resource-server adapter with a configured owner identity.
3. Test the official MCP SDK transport, persistent volume, ChatGPT connection, then Android device readback.
