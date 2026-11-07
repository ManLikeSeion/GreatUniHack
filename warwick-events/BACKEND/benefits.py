"""Keep free admission distinct from free refreshments."""
import re


def event_benefits(event):
    text = ' '.join(str(event.get(key) or '') for key in ('title', 'description')).lower()
    food = event.get('freeFood') is True
    entry = event.get('freeEntry') is True
    food_reason = 'marked by the organiser' if food else ''
    entry_reason = 'marked by the organiser' if entry else ''
    likely_food = False
    if re.search(r'\b(?:free|complimentary)\s+(?:food|pizza|snacks|refreshments|lunch|dinner|breakfast|buffet|meal|drinks)\b', text) and not re.search(r'\b(?:no|not|without)\s+free\s+(?:food|pizza|snacks|refreshments|lunch|dinner|breakfast|buffet|meal|drinks)\b', text):
        food = True
        food_reason = 'the event announcement explicitly offers free refreshments'
    elif not food and re.search(r'\blangar\b', str(event.get('title', '')).lower()):
        food = True
        likely_food = True
        food_reason = 'langar traditionally offers a free community meal; confirm with the organiser'
    if re.search(r'\b(?:free\s+(?:entry|admission|event)|(?:entry|admission)\s+is\s+free|no\s+(?:entry fee|admission fee)|free\s+to\s+attend)\b|\b(?:entry|admission|tickets?)\s*[:=-]?\s*£\s*0(?:\.00)?\b', text) and not re.search(r'\b(?:no|not)\s+free\s+(?:entry|admission)\b', text):
        entry = True
        entry_reason = 'the event announcement explicitly states free admission'
    return {**event, 'freeFood': food, 'freeEntry': entry, 'likelyFreeFood': likely_food,
            'freeFoodReason': food_reason, 'freeEntryReason': entry_reason}
