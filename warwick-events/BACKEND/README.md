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
For runtime dependencies alone, install `-r requirements.txt`.

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
