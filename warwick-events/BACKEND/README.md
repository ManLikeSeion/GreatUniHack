# Warwick Events API

See [the frontend guide](../FRONTEND/README.md) for full setup and the connected demo flow.

Run these commands in PowerShell from the repository root (reuse the root virtual environment):

```powershell
.\.venv\Scripts\python.exe -m pip install -r warwick-events/BACKEND/requirements-dev.txt
cd warwick-events/frontend
npm.cmd start
```

If `.venv` already exists, reuse it and skip the creation command. Activation is
optional because these commands invoke the virtual environment's Python directly.
On macOS/Linux use `.venv/bin/python` instead of `.\.venv\Scripts\python.exe`.
For runtime dependencies alone, install `-r warwick-events/BACKEND/requirements.txt` from the repository root.

The server runs at http://127.0.0.1:8000. Interactive API documentation at
http://127.0.0.1:8000/docs lets you try all endpoints, including POST requests.
React at `http://localhost:5173` is permitted by CORS.

In another PowerShell terminal:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/events
$eventBody = @{
    title = 'Society meetup'
    society = 'Example Warwick Society'
    category = 'social'
    source = 'manual'
    confidence = 1.0
    needs_review = $true
    review_reasons = @('Date and location not confirmed')
} | ConvertTo-Json
$created = Invoke-RestMethod http://127.0.0.1:8000/events -Method Post -ContentType 'application/json' -Body $eventBody
Invoke-RestMethod "http://127.0.0.1:8000/events/$($created.id)"
```

POST returns HTTP 201 for new events and HTTP 200 for exact duplicates. Invalid
data returns 422; a missing event returns 404. The shared Event model is unchanged.

The imported events API persists in `BACKEND/events.sqlite3`. From `warwick-events`,
import seed data with `..\.venv\Scripts\python.exe -m BACKEND.ingest BACKEND/examples/seed_events.json`.
Identical records are skipped. `/events` supports `q`, `category` and `upcoming` filters.

The frontend `/api` workflow remains available: AI extraction, private drafts,
reviewed publication, personal plans and live updates. It uses a separate database
at `BACKEND/data/common.sqlite3`. Imported `/events` records do not automatically
appear in `/api/catalog`. See the frontend guide for the reviewed publication flow.

Run the automated API and schema tests from `warwick-events`:

```powershell
..\.venv\Scripts\python.exe -m unittest discover -s BACKEND/tests -v
```

Tests use temporary SQLite databases and fresh applications. The development
requirements include the existing project requirements and HTTPX for TestClient;
the test runner is Python's built-in unittest.

## Additional extraction endpoints and tests

Tests use temporary database files, never your local events database. They cover
restart persistence, validation, duplicate imports/POSTs, rollback, discovery
filters, stable ordering, 404 and CORS. The existing Starlette version may emit an
HTTPX deprecation warning; it does not prevent these tests from running.

The existing project `requirements.txt` is required by the development requirements.
Include it when you later commit/share the backend; no commits are made by setup.

## AI extraction (Adam's agent)

`POST /extract` accepts form fields `text`, `society_name`, `society_id` and an
optional `image` file. Supply text, an image, or both. Posters may be JPEG, PNG,
WebP or GIF, at most 5 MiB; captions are limited to 20,000 characters.

Install the updated backend dependencies with the command at the top of this
README. Set `ANTHROPIC_API_KEY` in your terminal or a local ignored `.env` file
in the repository root (Adam's extractor loads dotenv). Never commit credentials.
For example, set `$env:ANTHROPIC_API_KEY` locally, then launch uvicorn in that same
terminal. Requests invoke Adam's configured model and may incur provider charges.
His model selection is left unchanged; a real provider call still needs a smoke
check using your team's account.

With the server running, open http://127.0.0.1:8000/docs, expand POST /extract,
choose Try it out, enter a caption or upload a poster, then Execute. Text-only
PowerShell example:

```powershell
$drafts = Invoke-RestMethod http://127.0.0.1:8000/extract -Method Post -Body @{
    text = 'Board games on 13 November 2026 at 7pm in Rootes'
    society_name = 'Example Games Society'
}
$drafts.events | Format-List
```

Returns `{"events": [...]}` validated against the canonical shared schema. Draft
IDs are null and review flags are preserved. Extraction does not save events.
After reviewing/correcting a draft, submit it to POST /events to persist it. This
is not yet a server-enforced approval workflow or persistent submission session.
No events found returns `{"events": []}`. Invalid input returns 422, unsupported
media 415, oversized posters 413, missing/invalid credentials or rate limiting
503, provider timeouts 504, and extraction/provider failures 502. Error responses
do not include provider details. File content must be a real supported image;
provider rejection is reported as an extraction failure.

The bridge uses Adam's existing `agent/extract.py` unchanged and revalidates its
output against `shared/schema.py`. Frontends at localhost:3000, 127.0.0.1:3000 and
localhost:5173 are permitted by CORS. Tests mock the agent call, so running them
requires no API key and makes no paid calls.

## Extract and save in one request (Adam's /submit endpoint)

`POST /submit` accepts the same form fields and poster uploads as `/extract`,
with the same limits and error responses. It returns a JSON array of stored
Events with backend-assigned IDs (HTTP 200). Exact duplicates return existing
records. All events in a submission are saved in a single transaction.

Unlike `/extract`, `/submit` saves immediately, including events marked
`needs_review`. Those flags remain visible in the stored data; this endpoint
is not a review/publication gate. Use `/extract` when you want to review first.
No events found returns an empty array and saves nothing.

Try POST /submit in http://127.0.0.1:8000/docs, then GET /events to see the result.
Your API key may be in the root `.env` or `agent/.env`; both are gitignored.
Environment variables take precedence, followed by the root file, then agent/.env.
Restart the server after changing credentials.
