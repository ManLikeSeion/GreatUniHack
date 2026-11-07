# Warwick Events backend

Use Python 3.12. Run these commands in PowerShell from the repository root:

```powershell
cd warwick-events
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r BACKEND/requirements-dev.txt
.\.venv\Scripts\python.exe -m uvicorn BACKEND.main:app --reload
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
Invoke-RestMethod http://127.0.0.1:8000/events/sample-1
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

POST returns HTTP 201 and assigns a UUID, replacing any supplied ID. Invalid data
returns 422; a missing event returns 404. Requests and responses use the existing
`shared/schema.py` Event model without changes. Initial sample data comes from
that module's validated EXAMPLE, with ID `sample-1`.

Data lives only in memory and resets on restart or reload. Use one server worker:
each worker would have its own store. There is no database, scraping or AI integration.

Run the automated API and schema tests from `warwick-events`:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s BACKEND/tests -v
```

Tests use a fresh application and in-memory store for each test. The development
requirements include the existing project requirements and HTTPX for TestClient;
the test runner is Python's built-in unittest.
