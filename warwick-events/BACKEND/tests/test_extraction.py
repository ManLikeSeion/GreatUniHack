import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import anthropic
from fastapi.testclient import TestClient

from BACKEND.main import create_app
from agent.schema import Event as AgentEvent
from shared.schema import EXAMPLE, Event


class ExtractionTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.client = self.enterContext(TestClient(
            create_app(Path(directory.name) / "events.sqlite3")))
        self.enterContext(patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-not-real"}))
        self.extractor = self.enterContext(patch("BACKEND.extraction.process_submission"))
        self.extractor.return_value = [AgentEvent.model_validate(EXAMPLE["events"][0])]

    def test_text_extracts_shared_drafts_without_saving(self):
        response = self.client.post("/extract", data={
            "text": "Games night Friday", "society_name": "Games Society"})
        self.assertEqual(response.status_code, 200)
        event = Event.model_validate(response.json()["events"][0])
        self.assertIsNone(event.id)
        self.extractor.assert_called_once_with(
            text="Games night Friday", image=None, image_media_type="image/jpeg",
            society_name="Games Society", society_id=None)
        self.assertEqual(self.client.get("/events").json(), [])
        # Explicit confirmation remains a separate, existing API operation.
        self.assertEqual(self.client.post("/events", json=event.model_dump(mode="json")).status_code, 201)

    def test_poster_and_caption_forwarded(self):
        response = self.client.post("/extract", data={"text": "Caption"},
                                    files={"image": ("poster.png", b"image-bytes", "image/png")})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.extractor.call_args.kwargs["image"], b"image-bytes")
        self.assertEqual(self.extractor.call_args.kwargs["image_media_type"], "image/png")

    def test_empty_and_invalid_input_rejected_before_ai_call(self):
        for data in [{}, {"text": "   "}, {"text": "x" * 20001}]:
            self.assertEqual(self.client.post("/extract", data=data).status_code, 422)
        for filename, content, media, expected in [
            ("a.pdf", b"pdf", "application/pdf", 415),
            ("a.png", b"", "image/png", 422),
            ("a.png", b"x" * (5 * 1024 * 1024 + 1), "image/png", 413),
        ]:
            response = self.client.post("/extract", files={"image": (filename, content, media)})
            self.assertEqual(response.status_code, expected)
        self.extractor.assert_not_called()

    def test_empty_result_and_review_flags_preserved(self):
        self.extractor.return_value = []
        self.assertEqual(self.client.post("/extract", data={"text": "Thanks everyone"}).json(),
                         {"events": []})
        event = AgentEvent.model_validate(EXAMPLE["events"][0])
        event.start = None
        event.id = "untrusted-id"
        event.needs_review = True
        event.review_reasons = ["Start time missing"]
        self.extractor.return_value = [event]
        draft = self.client.post("/extract", data={"text": "Meetup soon"}).json()["events"][0]
        self.assertIsNone(draft["id"])
        self.assertTrue(draft["needs_review"])
        self.assertEqual(draft["review_reasons"], ["Start time missing"])

    def test_failures_do_not_save_or_expose_internal_details(self):
        self.extractor.side_effect = RuntimeError("private upstream details")
        with self.assertLogs("BACKEND.main", level="ERROR"):
            response = self.client.post("/extract", data={"text": "Meetup"})
        self.assertEqual(response.status_code, 502)
        self.assertNotIn("private upstream details", response.text)
        self.assertEqual(self.client.get("/events").json(), [])

    def test_missing_key(self):
        with patch.dict(os.environ, {}, clear=True):
            response = self.client.post("/extract", data={"text": "Meetup"})
        self.assertEqual(response.status_code, 503)
        self.extractor.assert_not_called()

    def test_submit_stores_multiple_events_and_deduplicates(self):
        first = AgentEvent.model_validate(EXAMPLE["events"][0])
        second = first.model_copy(update={"title": "Another event", "needs_review": True})
        self.extractor.return_value = [first, second]
        response = self.client.post("/submit", data={"text": "Two events"})
        self.assertEqual(response.status_code, 200)
        stored = response.json()
        self.assertEqual(len(stored), 2)
        self.assertTrue(stored[1]["needs_review"])
        for event in stored:
            self.assertTrue(event["id"])
            self.assertEqual(self.client.get(f"/events/{event['id']}").json(), event)
        again = self.client.post("/submit", data={"text": "Two events"})
        self.assertEqual(again.json(), stored)
        self.assertEqual(len(self.client.get("/events").json()), 2)

    def test_submit_validation_and_extraction_failure_do_not_save(self):
        self.assertEqual(self.client.post("/submit").status_code, 422)
        self.extractor.assert_not_called()
        self.extractor.return_value = []
        self.assertEqual(self.client.post("/submit", data={"text": "No events"}).json(), [])
        self.extractor.side_effect = RuntimeError("private error")
        with self.assertLogs("BACKEND.main", level="ERROR"):
            response = self.client.post("/submit", data={"text": "Meetup"})
        self.assertEqual(response.status_code, 502)
        self.assertNotIn("private error", response.text)
        self.assertEqual(self.client.get("/events").json(), [])
