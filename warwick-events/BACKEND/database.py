"""Small SQLite store shared by the API and JSON importer."""

import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from uuid import uuid4

from shared.schema import Event

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "events.sqlite3"


class EventStore:
    def __init__(self, db_path=DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        with closing(self.connect()) as connection, connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY,
                    fingerprint TEXT NOT NULL UNIQUE,
                    payload TEXT NOT NULL
                )
            """)

    def connect(self):
        return sqlite3.connect(self.db_path, timeout=10)

    @staticmethod
    def _insert(connection, event):
        content = json.dumps(event.model_dump(mode="json", exclude={"id"}),
                             sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        fingerprint = hashlib.sha256(content.encode("utf-8")).hexdigest()
        stored = event.model_copy(update={"id": str(uuid4())})
        cursor = connection.execute(
            "INSERT INTO events (id, fingerprint, payload) VALUES (?, ?, ?) "
            "ON CONFLICT(fingerprint) DO NOTHING",
            (stored.id, fingerprint, stored.model_dump_json()),
        )
        if cursor.rowcount == 1:
            return stored, True
        payload = connection.execute(
            "SELECT payload FROM events WHERE fingerprint = ?", (fingerprint,)
        ).fetchone()[0]
        return Event.model_validate_json(payload), False

    def add(self, event: Event):
        with closing(self.connect()) as connection, connection:
            return self._insert(connection, event)

    def import_events(self, events: list[Event]):
        inserted = 0
        with closing(self.connect()) as connection, connection:
            for event in events:
                _, created = self._insert(connection, event)
                inserted += int(created)
        return {"inserted": inserted, "skipped": len(events) - inserted}

    def list_events(self) -> list[Event]:
        with closing(self.connect()) as connection:
            return [Event.model_validate_json(row[0]) for row in
                    connection.execute("SELECT payload FROM events")]

    def get(self, event_id: str) -> Event | None:
        with closing(self.connect()) as connection:
            row = connection.execute(
                "SELECT payload FROM events WHERE id = ?", (event_id,)
            ).fetchone()
        return Event.model_validate_json(row[0]) if row else None
