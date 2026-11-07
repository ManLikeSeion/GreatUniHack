"""Refresh the bundled official undergraduate catalog: python -m BACKEND.refresh_courses."""
import argparse
import json
import os
import re
import tempfile
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import urlopen
from zoneinfo import ZoneInfo

BASE_URL = 'https://warwick.ac.uk/study/undergraduate/courses/'
FEED_URL = 'https://sitebuilder.warwick.ac.uk/sitebuilder2/api/dataentry/entries.json?page=%2Fstudy%2Fundergraduate%2Fcourses%2Fcourse-list'
DEFAULT_OUTPUT = Path(__file__).resolve().parent / 'catalogs/courses.json'
# Explicit mappings of official Subject area labels. No LLM or inferred demographics.
SUBJECT_LABELS = {
    'accounting and finance': 'finance', 'artificial intelligence (ai)': 'ai',
    'biology (life sciences)': 'biology', 'business and management': 'business',
    'chemistry': 'chemistry', 'childhood studies': 'childhood-studies',
    'classics and ancient history': 'classics', 'computer science': 'computing',
    'counselling': 'counselling', 'creative writing': 'creative-writing',
    'cyber security': 'cyber-security', 'data science': 'data-science',
    'design studies': 'design', 'economics': 'economics', 'education': 'education',
    'engineering': 'engineering', 'english literature': 'literature',
    'film and television studies': 'film', 'global sustainable development': 'sustainability',
    'health sciences': 'health-sciences', 'history': 'history', 'history of art': 'art-history',
    'integrated natural sciences': 'natural-sciences', 'law': 'law',
    'liberal arts': 'liberal-arts', 'lifelong learning': 'lifelong-learning',
    'linguistics': 'linguistics', 'mathematics': 'mathematics',
    'media and creative industries': 'media', 'medical sciences': 'medicine',
    'modern languages and cultures': 'languages', 'morse': 'morse',
    'philosophy': 'philosophy', 'physics': 'physics',
    'politics and international studies': 'politics', 'psychology': 'psychology',
    'social work': 'social-work', 'society and culture': 'society-culture',
    'sociology': 'sociology', 'statistics': 'statistics',
    'theatre and performance studies': 'theatre',
}
# Literal title phrases add explicitly named subjects in joint degrees.
TITLE_SUBJECTS = {
    'mathematics': 'mathematics', 'statistics': 'statistics', 'physics': 'physics',
    'computer science': 'computing', 'data science': 'data-science',
    'chemistry': 'chemistry', 'biological sciences': 'biology',
    'economics': 'economics', 'psychology': 'psychology', 'philosophy': 'philosophy',
    'law': 'law', 'history': 'history', 'sociology': 'sociology',
    'engineering': 'engineering', 'english literature': 'literature',
    'politics': 'politics', 'accounting and finance': 'finance',
}


class CourseLinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_heading = False
        self.link = None

    def handle_starttag(self, tag, attrs):
        if tag == 'h3':
            self.in_heading = True
        if self.in_heading and tag == 'a' and self.link is None:
            self.link = dict(attrs).get('href')

    def handle_endtag(self, tag):
        if tag == 'h3':
            self.in_heading = False


def canonical_url(url):
    parts = urlsplit(url)
    if parts.scheme != 'https' or parts.netloc.lower() != 'warwick.ac.uk' or not parts.path.startswith('/study/undergraduate/courses/'):
        raise ValueError('Course link is outside the official directory')
    return urlunsplit(('https', 'warwick.ac.uk', parts.path.rstrip('/'), '', ''))


def build_snapshot(feed, previous):
    if not isinstance(feed, dict) or not isinstance(feed.get('items'), list) or not feed['items']:
        raise ValueError('Feed has no course records')
    old_by_url = {canonical_url(c['source_url']): c for c in previous.get('items', [])}
    by_url, rejected, unclassified, unknown_subjects = {}, [], [], set()
    for item in feed['items']:
        try:
            if not isinstance(item, dict):
                raise ValueError('Course record is not an object')
            categories = [c if isinstance(c, str) else c['name'] for c in item.get('categories', [])]
            if any(c.strip().casefold() == 'visibility: hidden' for c in categories):
                continue
            title = ' '.join(item['title'].split())
            parser = CourseLinkParser()
            parser.feed(item.get('content') or item.get('parsedContentBody') or '')
            if not title or not parser.link:
                raise ValueError('Missing course title or heading link')
            url = canonical_url(urljoin(BASE_URL, parser.link))
            previous_course = old_by_url.get(url, {})
            course_id = previous_course.get('id') or item.get('anchor')
            if not course_id or not re.fullmatch(r'[a-z0-9][a-z0-9-]*', course_id) or course_id == 'not-listed':
                raise ValueError('Missing or invalid stable ID')
            subjects = set()
            for category in categories:
                if category.startswith('Subject area: '):
                    subject = re.sub(r'\s+\(sa\d+\)$', '', category[len('Subject area: '):]).strip().casefold()
                    if subject in SUBJECT_LABELS:
                        subjects.add(SUBJECT_LABELS[subject])
                    else:
                        unknown_subjects.add(subject)
            for phrase, subject in TITLE_SUBJECTS.items():
                if re.search(r'\b' + re.escape(phrase) + r'\b', title, re.IGNORECASE):
                    subjects.add(subject)
            # Retain the legacy primary subject and exact URL for existing profiles.
            primary = previous_course.get('subject')
            if primary:
                subjects.add(primary)
            course = {'id': course_id, 'name': title, 'subject': primary or (sorted(subjects)[0] if subjects else None),
                      'subject_ids': sorted(subjects), 'source_url': previous_course.get('source_url', url)}
            if url in by_url:
                # Duplicate listings can contribute additional explicit subject metadata.
                existing = by_url[url]
                existing['subject_ids'] = sorted(set(existing['subject_ids']) | subjects)
                continue
            by_url[url] = course
        except (KeyError, TypeError, ValueError) as error:
            rejected.append({'name': item.get('title', '(unknown)') if isinstance(item, dict) else '(invalid record)', 'reason': str(error)})
    if rejected:
        raise ValueError('Rejected visible records; snapshot unchanged: ' + json.dumps(rejected))
    courses = sorted(by_url.values(), key=lambda c: (c['name'].casefold(), c['id']))
    if not courses or len({c['id'] for c in courses}) != len(courses):
        raise ValueError('Empty catalog or duplicate stable IDs')
    missing = {c['id'] for c in previous.get('items', [])} - {c['id'] for c in courses}
    if missing:
        raise ValueError('Existing course IDs missing from feed; review before removal: ' + ', '.join(sorted(missing)))
    unclassified = [c['id'] for c in courses if not c['subject_ids']]
    snapshot = {'version': 2, 'retrieved_on': datetime.now(ZoneInfo('Europe/London')).date().isoformat(),
                'curated': False, 'scope': 'visible-undergraduate-feed', 'source_url': FEED_URL, 'items': courses}
    return snapshot, {'courses': len(courses), 'unclassified_ids': unclassified,
                      'unknown_subject_labels': sorted(unknown_subjects)}


def refresh(output=DEFAULT_OUTPUT, feed=None):
    output = Path(output)
    previous = json.loads(output.read_text(encoding='utf-8')) if output.exists() else {'items': []}
    if feed is None:
        with urlopen(FEED_URL, timeout=30) as response:
            feed = json.load(response)
    snapshot, report = build_snapshot(feed, previous)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='\n', dir=output.parent,
                                         prefix='courses-', suffix='.tmp', delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(snapshot, handle, indent=2, ensure_ascii=True)
            handle.write('\n')
        os.replace(temporary, output)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--feed-file', type=Path, help='Use a previously downloaded feed for offline refresh/testing')
    args = parser.parse_args()
    try:
        feed = json.loads(args.feed_file.read_text(encoding='utf-8')) if args.feed_file else None
        print(json.dumps(refresh(args.output, feed), indent=2))
    except (OSError, ValueError, TypeError) as error:
        parser.exit(1, f'Course refresh failed: {error}\n')


if __name__ == '__main__':
    main()
