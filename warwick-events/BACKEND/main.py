"""Persistent events API. Run from warwick-events: uvicorn BACKEND.main:app."""

from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware

from BACKEND.database import DEFAULT_DB_PATH, EventStore
from shared.schema import Category, Event


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
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

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
