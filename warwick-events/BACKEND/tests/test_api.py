"""Run from warwick-events: python -m unittest discover -s BACKEND/tests -v."""

import unittest
from copy import deepcopy

from fastapi.testclient import TestClient
from pydantic import ValidationError

from BACKEND.main import create_app
from shared.schema import EXAMPLE, Event


class EventsAPITests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(create_app())
        self.addCleanup(self.client.close)
        self.payload = deepcopy(EXAMPLE["events"][0])

    def test_health(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_samples_conform_to_shared_schema_and_can_be_retrieved(self):
        response = self.client.get("/events")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json())
        for item in response.json():
            event = Event.model_validate(item)
            self.assertIsNotNone(event.id)
            detail = self.client.get(f"/events/{event.id}")
            self.assertEqual(detail.status_code, 200)
            self.assertEqual(detail.json(), item)

    def test_missing_event(self):
        response = self.client.get("/events/missing")
        self.assertEqual(response.status_code, 404)

    def test_create_assigns_unique_ids_and_preserves_existing_events(self):
        original = self.client.get("/events/sample-1").json()
        self.payload["id"] = "sample-1"
        first = self.client.post("/events", json=self.payload)
        second = self.client.post("/events", json=self.payload)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        event = Event.model_validate(first.json())
        self.assertNotEqual(event.id, "sample-1")
        self.assertNotEqual(event.id, second.json()["id"])
        self.assertEqual(self.client.get(f"/events/{event.id}").json(), first.json())
        self.assertEqual(self.client.get("/events/sample-1").json(), original)
        self.assertEqual(len(self.client.get("/events").json()), 3)

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
        self.assertEqual(len(self.client.get("/events").json()), 1)

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
