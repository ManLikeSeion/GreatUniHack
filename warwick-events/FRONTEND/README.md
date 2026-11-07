# common: campus events prototype

## run locally (windows powershell)

Run these setup commands once from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r warwick-events/BACKEND/requirements.txt
```

Copy `.env.example` to `.env` in the repository root, then enter your `ANTHROPIC_API_KEY` and an `ANTHROPIC_MODEL` ID available in your account. Keep both server-side. Without these settings, manual event creation and clearly labelled basic event search still work; AI poster/text extraction reports that configuration is required.

Start both servers:

```powershell
cd warwick-events/FRONTEND
npm.cmd start
```

Open http://localhost:3000. Stop any older frontend server first with Ctrl+C. Port 8000 hosts the Python API; the Node server proxies `/api` requests to it. `npm.cmd` avoids PowerShell's npm.ps1 execution-policy issue. No Node dependency installation is needed. On macOS/Linux use `.venv/bin/python` for setup and `npm start`.

## demo flow

1. Choose exec and enter a demo email.
2. Open make an event. Paste an announcement and/or upload a JPEG, PNG or WebP poster under 4 MB. Enter the society name and extract event details. Submitted content is sent to Anthropic only after pressing extract.
3. Each extracted event becomes a private draft. Select a draft and inspect missing fields, low confidence, uncertain duration and possible duplicate warnings. You can also fill in the form manually and save a draft.
4. Correct the date, time, duration, location and description. Confirm the human-review checkbox, then approve and publish. Required fields, future dates, clock-change ambiguity and duplicates are checked on the server. Duplicate publication is blocked.
5. Open another browser tab and sign in as a student. Published events appear in Discover and the calendar. Likes and sign-ups persist in SQLite per email. Live updates use authenticated server-sent events with five-second polling as a fallback.
6. Open ask your campus companion on Discover. Try ?free food tomorrow without clashes?. With AI configured, natural language becomes validated search filters. Results are selected by code from published database events and checked against your liked/signed-up plans. Without AI, basic search supports category names, today, tomorrow, ISO dates, free food and no-clash requests.
7. Set interests in settings. Recommendations prioritise those categories. Recent chat history and saved plans survive server restarts.

## roles and boundaries

Student: discover, assistant and personal calendar. Exec: student features plus draft extraction, review and publication. External: local vendor promotion/payment preview (no charges or ad delivery).

Identity remains a self-selected demo email and role, not Warwick SSO. Sessions are opaque server-side tokens expiring after 12 hours; protected routes enforce the selected role and private-draft ownership. Do not treat this as production authentication. Sign-ups record intent, not a registration with a society.

Official requests stay pending. This UI cannot grant a university-verified official badge. Free food is confirmed by the reviewer rather than inferred from uncertain AI output. Uploaded text is treated as untrusted source data, not agent instructions. AI has no publication or database-writing tool.

The shared catalog includes reviewed events and records imported through the backend events API. Records without a start time are omitted; review flags remain visible. Earlier browser-local events and fictional repeating samples are not automatically imported. SQLite data lives in ignored `warwick-events/BACKEND/data/`. The persistent `/events` API and seed importer feed the same frontend catalog through a server-side adapter. UK times, stable imported IDs, duplicate suppression, likes, clashes and live updates work across both sources.

Afacad and event photos load from external services; fallbacks remain when offline. Tab transitions and clash animations respect reduced-motion settings.

## checks

From the repository root:

```powershell
npm.cmd --prefix warwick-events/FRONTEND run check
```

From `warwick-events`:

```powershell
..\.venv\Scripts\python.exe -m unittest discover -s BACKEND/tests -v
```

Workflow tests use temporary SQLite databases and a stub extractor, never a paid model call. A real extraction smoke test requires your configured AI account.
