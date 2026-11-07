# Warwick Events API

See [the frontend guide](../FRONTEND/README.md) for full setup and the connected demo flow.

From the repository root, install `warwick-events/BACKEND/requirements.txt` into the root `.venv`. Then run `npm.cmd start` in `warwick-events/FRONTEND` to launch both servers. To run only the API:

```powershell
.\.venv\Scripts\python.exe warwick-events/BACKEND/run.py
```

API docs: http://127.0.0.1:8000/docs. Health: `/health`.

## reviewed workflow

- `POST /api/session`: demo email/role login; returns a 12-hour bearer token.
- `DELETE /api/session`: revoke the current token.
- `GET /api/state`: profile, recent chat history, role and AI availability.
- `GET /api/catalog`: shared published events.
- `GET /api/updates`: authenticated server-sent catalog updates.
- `POST /api/extract`: exec-only caption/base64-poster extraction into private drafts.
- `GET /api/drafts`: current exec's drafts.
- `POST /api/drafts`: manually create a private draft.
- `POST /api/drafts/{id}/publish`: owner/exec review gate, validation and duplicate checks.
- `PUT /api/plans`: save likes, sign-ups and interests per email.
- `POST /api/assistant`: natural-language filters, database-grounded recommendations and clash checks. Falls back to labelled basic search if AI is unavailable.

All `/api` routes except login require `Authorization: Bearer <token>`. Demo roles are self-selected, not verified institutional identities. Official requests remain pending; no public client can award verified status. The AI can only extract event data or propose search filters; deterministic code handles validation, storage and publication.

SQLite persists under ignored `BACKEND/data/`. Text/poster extraction reuses `agent/extract.py` without changing the shared schema. AI credentials and model configuration are read from the root `.env`. Raw poster files are not stored. Images are validated before submission to the model.

## legacy contract

`GET /events`, `GET /events/{id}` and `POST /events` retain the team's original shared-schema, in-memory API and sample event. They do not write to the reviewed catalog. Existing integrations and tests can continue to use them.

## tests

From `warwick-events`:

```powershell
..\.venv\Scripts\python.exe -m unittest discover -s BACKEND/tests -v
```

Tests cover the legacy API plus draft privacy, publication validation, duplicates, persistence, role checks, image validation, saved plans, grounded recommendations, chat history and session revocation. Extraction uses a stub, so tests do not incur provider charges.
