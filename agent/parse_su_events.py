"""Turn the pasted text of the Warwick SU "Societies Events" page into schema Events.

Usage (from inside agent/):
    python parse_su_events.py su_page.txt                 # writes seed_events.json
    python parse_su_events.py su_page.txt -o out.json --from 2026-11-07

Deterministic, no AI: dates, times, titles and locations come straight from the
calendar grid. Society names come from the list below the calendar where shown,
otherwise from title patterns, otherwise "Warwick SU". Categories are keyword
guesses, so skim the output before the demo.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

try:
    from .schema import Event, ExtractionResult
except ImportError:  # running as a script from inside agent/
    from schema import Event, ExtractionResult

LONDON = ZoneInfo("Europe/London")
MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], start=1)}
FULL_MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"], start=1)}

DAY = re.compile(r"^\d{1,2}$")
TIME = re.compile(r"^(\d{2}):(\d{2})\s*[-–]\s*(\d{2}):(\d{2})$")
SPAN = re.compile(r"^(\d{1,2}) ([A-Za-z]{3})\s*[-–]\s*(\d{1,2}) ([A-Za-z]{3})$")
WEEKDAYS = re.compile(r"^M\s+T\s+W\s+T\s+F\s+S\s+S$")
HEADER = re.compile(r"^(" + "|".join(FULL_MONTHS) + r") (\d{4})$")

SOCIETY_PATTERNS = [
    (r"^Warwick Student Cinema", "Warwick Student Cinema"),
    (r"^Who Soc", "Who Soc"),
    (r"Environmental Coalition", "Environmental Coalition"),
    (r"Christian Union", "Christian Union"),
    (r"^Warwick Darts", "Warwick Darts"),
    (r"DofE", "Warwick DofE"),
    (r"Warwick Salsa", "Warwick Salsa"),
]

# Order matters: first matching rule wins.
CATEGORY_RULES = [
    ("charity", ["for the rspb", "charity", "fundrais"]),
    ("cultural", ["mehfil", "langar", "pepero", "arayes", "mauritian", "warisan", "christian union", "latin night"]),
    ("academic", ["whack", "hackathon", "lecture", "seminar"]),
    ("sports", ["yoga", "vinyasa", "darts", "karting", "banbury", "dofe", "tournament", "sports"]),
    ("arts", ["cinema", "film", "screening", "art journaling", "still life", "workshop", "concert", "all-nighter"]),
    ("social", ["clubnight", "mayhem", "euphoria", "360", "bowling", "quiz", "trip", "night"]),
]


def guess_category(title: str) -> str:
    t = title.lower()
    for category, words in CATEGORY_RULES:
        if any(w in t for w in words):
            return category
    return "other"


def guess_society(title: str, listed: dict[str, str]) -> str:
    if title in listed:
        return listed[title]
    for pattern, name in SOCIETY_PATTERNS:
        if re.search(pattern, title):
            return name
    return "Warwick SU"


def tidy(title: str) -> str:
    return re.sub(r"^[^\w'\"(]+", "", title).strip()  # drop leading emoji


def is_marker(line: str) -> bool:
    return bool(DAY.match(line) or TIME.match(line) or SPAN.match(line))


def parse_listed_societies(lines: list[str]) -> dict[str, str]:
    """The list under the calendar gives: title, society, date line, 'Location: ...'."""
    out: dict[str, str] = {}
    for i, line in enumerate(lines):
        if line.startswith("Location:") and i >= 3:
            title, society = lines[i - 3], lines[i - 2]
            if title and society:
                out[title] = society
    return out


def parse(text: str, from_date: date) -> list[Event]:
    lines = [ln.strip() for ln in text.splitlines()]

    header_year, header_month = 2026, 11
    for ln in lines:
        m = HEADER.match(ln.replace("\t", " ").strip("<> \t"))
        if m:
            header_month, header_year = FULL_MONTHS[m.group(1)], int(m.group(2))
            break

    start_idx = next(i for i, ln in enumerate(lines) if WEEKDAYS.match(ln)) + 1
    end_idx = next((i for i in range(start_idx, len(lines)) if lines[i] == ""), len(lines))
    cal = lines[start_idx:end_idx]
    listed = parse_listed_societies(lines[end_idx:])

    events: list[Event] = []
    seen_spans: set[tuple[str, str]] = set()
    current: date | None = None
    prev_day = 0
    month, year = header_month, header_year

    i = 0
    while i < len(cal):
        line = cal[i]
        if DAY.match(line):
            d = int(line)
            if current is None:
                if d > 15:  # grid starts in the previous month
                    month -= 1
                    if month == 0:
                        month, year = 12, year - 1
            elif d < prev_day:
                month += 1
                if month == 13:
                    month, year = 1, year + 1
            prev_day = d
            current = date(year, month, d)
            i += 1
            continue

        tm, sm = TIME.match(line), SPAN.match(line)
        if (tm or sm) and current is not None:
            title = tidy(cal[i + 1]) if i + 1 < len(cal) else ""
            location = None
            step = 2
            if i + 2 < len(cal) and not is_marker(cal[i + 2]):
                location, step = cal[i + 2], 3
            i += step
            if not title:
                continue

            reasons: list[str] = []
            if tm:
                sh, sMin, eh, eMin = (int(x) for x in tm.groups())
                start = datetime.combine(current, time(sh, sMin), tzinfo=LONDON)
                end = datetime.combine(current, time(eh, eMin), tzinfo=LONDON)
                if end <= start:
                    end += timedelta(days=1)
            else:
                key = (title, line)
                if key in seen_spans:
                    continue
                seen_spans.add(key)
                d1, m1, d2, m2 = int(sm.group(1)), MONTHS[sm.group(2)], int(sm.group(3)), MONTHS[sm.group(4)]
                first, last = date(current.year, m1, d1), date(current.year, m2, d2)
                start = datetime.combine(first, time(0, 0), tzinfo=LONDON)
                end = datetime.combine(last, time(23, 59), tzinfo=LONDON)
                if first == last:
                    reasons.append("No start time on the SU calendar; shown as all day")

            if end.date() < from_date:
                continue
            events.append(Event(
                title=title,
                society=guess_society(title, listed),
                category=guess_category(title),
                start=start,
                end=end,
                location=location,
                source="scrape",
                confidence=0.95 if not reasons else 0.7,
                needs_review=bool(reasons),
                review_reasons=reasons,
            ))
            continue
        i += 1

    events.sort(key=lambda e: e.start)
    return events


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("page_text", help="text file containing the pasted SU events page")
    ap.add_argument("-o", "--out", default="seed_events.json")
    ap.add_argument("--from", dest="from_date", default=date.today().isoformat(),
                    help="drop events that ended before this date (YYYY-MM-DD)")
    args = ap.parse_args()

    events = parse(Path(args.page_text).read_text(encoding="utf-8"), date.fromisoformat(args.from_date))
    result = ExtractionResult(events=events)
    Path(args.out).write_text(
        json.dumps(result.model_dump(mode="json", exclude_none=True), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Wrote {len(events)} events to {args.out}")
    print("By category:", dict(Counter(e.category for e in events)))
    print("Flagged for review:", [e.title for e in events if e.needs_review])
    print("Society fallback ('Warwick SU'):", sum(e.society == "Warwick SU" for e in events))


if __name__ == "__main__":
    main()
