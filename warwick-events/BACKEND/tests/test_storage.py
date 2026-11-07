"""Persistence, ingestion and discovery integration tests."""
import json
import sqlite3
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import ValidationError

from BACKEND.database import EventStore
from BACKEND.ingest import import_file
from BACKEND.main import create_app
from shared.schema import EXAMPLE, Event


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / 'events.sqlite3'
        self.file = Path(self.temp.name) / 'events.json'
        self.payload = dict(EXAMPLE['events'][0])

    def test_import_twice_and_api_share_duplicates(self):
        self.file.write_text(json.dumps(EXAMPLE), encoding='utf-8')
        self.assertEqual(import_file(self.file, self.db), {'inserted': 1, 'skipped': 0})
        self.assertEqual(import_file(self.file, self.db), {'inserted': 0, 'skipped': 1})
        with TestClient(create_app(self.db)) as client:
            self.assertEqual(client.post('/events', json=self.payload).status_code, 200)
            self.assertEqual(len(client.get('/events').json()), 1)

    def test_invalid_batch_does_not_write(self):
        self.file.write_text(json.dumps({'events': [self.payload, {'title': 'invalid'}]}))
        with self.assertRaises(ValidationError):
            import_file(self.file, self.db)
        self.assertFalse(self.db.exists())

    def test_database_error_rolls_back_entire_batch(self):
        store = EventStore(self.db)
        original = store._insert
        calls = 0

        def fail_second(connection, event):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise sqlite3.OperationalError('simulated failure')
            return original(connection, event)

        event = Event.model_validate(self.payload)
        with patch.object(store, '_insert', side_effect=fail_second):
            with self.assertRaises(sqlite3.OperationalError):
                store.import_events([event, event.model_copy(update={'title': 'Second'})])
        self.assertEqual(store.list_events(), [])

    def test_filters_and_ordering(self):
        now = datetime.now(timezone.utc)
        with TestClient(create_app(self.db)) as client:
            for title, society, category, start in [
                ('Future A', 'Computing Society', 'academic', now + timedelta(days=2)),
                ('Future B', 'Sports Club', 'sports', now + timedelta(days=1)),
                ('Past', 'Computing Society', 'academic', now - timedelta(days=1)),
                ('Unknown', 'Computing Society', 'academic', None),
            ]:
                payload = dict(self.payload, title=title, society=society,
                               category=category, start=start.isoformat() if start else None)
                self.assertEqual(client.post('/events', json=payload).status_code, 201)
            def titles(params=None):
                return [e['title'] for e in client.get('/events', params=params).json()]
            self.assertEqual(titles(), ['Past', 'Future B', 'Future A', 'Unknown'])
            self.assertEqual(titles({'upcoming': True}), ['Future B', 'Future A'])
            self.assertEqual(titles({'q': 'COMPUTING', 'category': 'academic',
                                     'upcoming': True}), ['Future A'])
            self.assertEqual(titles({'q': 'future b'}), ['Future B'])
            self.assertEqual(titles({'q': 'missing'}), [])
            self.assertEqual(client.get('/events?category=invalid').status_code, 422)
            self.assertEqual(client.get('/events?upcoming=invalid').status_code, 422)

    def test_equal_start_times_use_id_tiebreaker(self):
        store = EventStore(self.db)
        first, _ = store.add(Event.model_validate(self.payload))
        second, _ = store.add(Event.model_validate(dict(self.payload, title='Second')))
        with TestClient(create_app(self.db)) as client:
            ids = [e['id'] for e in client.get('/events').json()]
            self.assertEqual(ids, sorted([first.id, second.id]))
