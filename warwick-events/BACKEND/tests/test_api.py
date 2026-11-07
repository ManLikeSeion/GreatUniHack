"""Run from warwick-events: python -m unittest discover -s BACKEND/tests -v."""

import unittest
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient
from pydantic import ValidationError

from BACKEND.main import create_app
from shared.schema import EXAMPLE, Event


class EventsAPITests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db_path = Path(self.temp.name) / "test.sqlite3"
        self.client = self.enterContext(TestClient(create_app(self.db_path)))
        self.payload = deepcopy(EXAMPLE["events"][0])

    def test_health(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_empty_startup_and_persistence(self):
        self.assertEqual(self.client.get("/events").json(), [])
        created = self.client.post("/events", json=self.payload).json()
        Event.model_validate(created)
        with TestClient(create_app(self.db_path)) as restarted:
            self.assertEqual(restarted.get(f"/events/{created['id']}").json(), created)
            self.assertEqual(restarted.get("/events").json(), [created])

    def test_missing_event(self):
        response = self.client.get("/events/missing")
        self.assertEqual(response.status_code, 404)

    def test_create_assigns_ids_and_skips_duplicates(self):
        self.payload["id"] = "client-id"
        first = self.client.post("/events", json=self.payload)
        self.payload["id"] = "another-client-id"
        second = self.client.post("/events", json=self.payload)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertNotEqual(first.json()["id"], "client-id")
        self.assertEqual(first.json(), second.json())
        self.payload["title"] = "Different event"
        third = self.client.post("/events", json=self.payload)
        self.assertEqual(third.status_code, 201)
        self.assertNotEqual(third.json()["id"], first.json()["id"])
        self.assertEqual(len(self.client.get("/events").json()), 2)

    def test_invalid_payloads_are_rejected_without_storing(self):
        for field, value in [("category", "invalid"), ("confidence", 1.1),
                             ("confidence", -0.1), ("start", "not-a-date")]:
            with self.subTest(field=field, value=value):
                payload = dict(self.payload, **{field: value})
                with self.assertRaises(ValidationError):
                    Event.model_validate(payload)
                self.assertEqual(self.client.post("/events", json=payload).status_code, 422)
        del self.payload["title"]
        self.assertEqual(self.client.post("/events", json=self.payload).status_code, 422)
        self.assertEqual(len(self.client.get("/events").json()), 0)

    def test_unknown_details_can_remain_null(self):
        self.payload.update(start=None, end=None, location=None, needs_review=True)
        response = self.client.post("/events", json=self.payload)
        self.assertEqual(response.status_code, 201)
        self.assertIsNone(response.json()["start"])
        self.assertIsNone(response.json()["location"])

    def test_cors_preflight(self):
        for origin, allowed in [("http://localhost:5173", True),
                                ("https://example.com", False)]:
            with self.subTest(origin=origin):
                response = self.client.options("/events", headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "content-type",
                })
                self.assertEqual(response.status_code, 200 if allowed else 400)
                self.assertEqual(response.headers.get("access-control-allow-origin"),
                                 origin if allowed else None)


if __name__ == "__main__":
    unittest.main()
