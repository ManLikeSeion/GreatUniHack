# Warwick Events backend

Use Python 3.12. In PowerShell from the repository root:

```powershell
cd warwick-events
# Skip this if .venv already exists:
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r BACKEND/requirements-dev.txt
.\.venv\Scripts\python.exe -m uvicorn BACKEND.main:app --reload
```

Leave that terminal running. Open http://127.0.0.1:8000/docs to try the API.
React or another frontend at http://localhost:5173 is allowed by CORS.
On macOS/Linux use `.venv/bin/python` instead of `.\.venv\Scripts\python.exe`.
For runtime dependencies alone install `-r requirements.txt`.

## Storage and importing

New databases start empty. Events persist in `BACKEND/events.sqlite3`, independent
of the current working directory. SQLite database and journal files are ignored
by Git. Never commit your database. API responses use the unchanged shared Event
model; IDs are always assigned by the backend.

From `warwick-events`, import clearly labelled fictional demo data:

```powershell
.\.venv\Scripts\python.exe -m BACKEND.ingest BACKEND/examples/sample-events.json
```

Expected: `Inserted: 1; skipped: 0`. Run again: `Inserted: 0; skipped: 1`.
Adam can supply any UTF-8 JSON file shaped as `{"events": [...]}` matching
`shared.schema.ExtractionResult`, without supplying event IDs. The whole file is
validated before writing; a database failure rolls back the entire batch.
Invalid files print an error and exit nonzero. Use `--db PATH` to import into a
separate database (its parent directory must exist).

Exact duplicates are detected from all validated Event fields except `id`, using
canonical JSON and a unique SHA-256 fingerprint. Missing optional fields and
explicit defaults match. Differences in text, metadata or dates count as different
content; this is not fuzzy matching or update detection. POST and imports share
this logic, including across server restarts.

## API and demo

In a second PowerShell terminal:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/events
Invoke-RestMethod 'http://127.0.0.1:8000/events?q=muay&category=sports'
$eventBody = @{
    title = '[DEMO SAMPLE] Society meetup'
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

Stop the server with Ctrl+C, restart with the same uvicorn command, then repeat
that last GET in the second terminal: the event and ID survive restart.

- `GET /health`: returns `{"status":"ok"}` (process health).
- `GET /events`: returns an array; optional `q` searches title or society by
  case-insensitive substring, `category` filters by the schema's category values,
  and `upcoming=true` excludes past events and events with unknown dates.
- Filters combine with AND. Events sort by start time, unknown dates last, then ID.
  Supply explicit timezone offsets, as required by the shared contract; legacy
  timestamps without offsets are interpreted as UTC for filtering and ordering.
- `GET /events/{id}`: event or HTTP 404.
- `POST /events`: new event with server-assigned UUID and HTTP 201; exact duplicates
  return the existing event and HTTP 200. Invalid input returns 422.

No automatic sample seeding, scraping, LLM calls, authentication or deployment is
included. This is a local demo API. Source URL support remains a proposed shared
schema addition to coordinate with Adam and Seion; it has not been implemented.

## Tests

From `warwick-events`:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s BACKEND/tests -v
.\.venv\Scripts\python.exe -m pip check
```

Tests use temporary database files, never your local events database. They cover
restart persistence, validation, duplicate imports/POSTs, rollback, discovery
filters, stable ordering, 404 and CORS. The existing Starlette version may emit an
HTTPX deprecation warning; it does not prevent these tests from running.

The existing project `requirements.txt` is required by the development requirements.
Include it when you later commit/share the backend; no commits are made by setup.
