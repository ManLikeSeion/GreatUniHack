"""Persistent events API. Run from warwick-events: uvicorn BACKEND.main:app."""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import logging

import anthropic
from fastapi import Depends, FastAPI, File, Form, HTTPException, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from BACKEND.database import DEFAULT_DB_PATH, EventStore
from BACKEND.extraction import ExtractionNotConfigured, extract_events
from shared.schema import Category, Event, ExtractionResult

log = logging.getLogger(__name__)
MAX_IMAGE_BYTES = 5 * 1024 * 1024


def event_time(event: Event) -> datetime:
    # Legacy offset-free timestamps use UTC; producers should supply explicit offsets.
    value = event.start
    if value is None:
        return datetime.max.replace(tzinfo=timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def create_app(db_path=DEFAULT_DB_PATH) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app):
        app.state.store = EventStore(db_path)
        yield

    app = FastAPI(title="Warwick Events API", lifespan=lifespan)
    from BACKEND.workflow import create_workflow
    app.include_router(create_workflow(event_provider=lambda: app.state.store.list_events()), prefix="/api")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:3000"],
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type", "Authorization"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/extract", response_model=ExtractionResult)
    def extract_submission(
        text: str | None = Form(None, max_length=20000),
        society_name: str | None = Form(None, max_length=200),
        society_id: str | None = Form(None, max_length=200),
        image: UploadFile | None = File(None),
    ) -> ExtractionResult:
        """Extract drafts for review. Does not publish or save events."""
        text = text.strip() if text else None
        image_bytes = None
        media_type = "image/jpeg"
        if image is not None:
            media_type = image.content_type or ""
            if media_type not in {"image/jpeg", "image/png", "image/webp", "image/gif"}:
                raise HTTPException(415, "Upload a JPEG, PNG, WebP or GIF poster")
            image_bytes = image.file.read(MAX_IMAGE_BYTES + 1)
            if len(image_bytes) > MAX_IMAGE_BYTES:
                raise HTTPException(413, "Poster must be no larger than 5 MiB")
            if not image_bytes:
                raise HTTPException(422, "Poster is empty")
        if not text and not image_bytes:
            raise HTTPException(422, "Provide announcement text, a poster, or both")
        try:
            return extract_events(text=text, image=image_bytes,
                                  image_media_type=media_type,
                                  society_name=society_name, society_id=society_id)
        except anthropic.APITimeoutError:
            raise HTTPException(504, "Extraction service timed out; try again") from None
        except anthropic.RateLimitError:
            raise HTTPException(503, "Extraction service is busy; try again later") from None
        except (ExtractionNotConfigured, anthropic.AuthenticationError, anthropic.PermissionDeniedError):
            raise HTTPException(503, "Extraction service credentials need configuration") from None
        except (anthropic.APIError, RuntimeError, ValidationError, ValueError):
            log.exception("Event extraction failed")
            raise HTTPException(502, "Could not extract events; try again or revise the submission") from None

    @app.post("/submit", response_model=list[Event])
    def submit_submission(
        drafts: ExtractionResult = Depends(extract_submission),
    ) -> list[Event]:
        """Extract and immediately store all events, including flagged events."""
        return [event for event, _ in app.state.store.add_batch(drafts.events)]

    @app.get("/events", response_model=list[Event])
    def list_events(q: str | None = None, category: Category | None = None,
                    upcoming: bool = False) -> list[Event]:
        events = app.state.store.list_events()
        now = datetime.now(timezone.utc)
        if q is not None:
            events = [e for e in events if q.casefold() in e.title.casefold()
                      or q.casefold() in e.society.casefold()]
        if category is not None:
            events = [e for e in events if e.category == category]
        if upcoming:
            events = [e for e in events if e.start is not None and event_time(e) >= now]
        return sorted(events, key=lambda e: (e.start is None, event_time(e), e.id))

    @app.get("/events/{event_id}", response_model=Event)
    def get_event(event_id: str) -> Event:
        event = app.state.store.get(event_id)
        if event is None:
            raise HTTPException(status_code=404, detail="Event not found")
        return event

    @app.post("/events", response_model=Event, status_code=status.HTTP_201_CREATED)
    def create_event(event: Event, response: Response) -> Event:
        stored, created = app.state.store.add(event)
        if not created:
            response.status_code = status.HTTP_200_OK
        return stored

    return app


app = create_app()
