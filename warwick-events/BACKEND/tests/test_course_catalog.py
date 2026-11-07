import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from BACKEND.refresh_courses import build_snapshot, refresh


def record(title, slug, categories=None, anchor=None):
    return {'title': title, 'anchor': anchor or slug,
            'content': f'<h3><a href="{slug}">Official course</a></h3>',
            'categories': categories or []}


class CourseCatalogTests(unittest.TestCase):
    def test_visible_courses_sorted_joint_subjects_and_deduplicated(self):
        feed = {'items': [
            record('Zoology BSc', 'zoology'),
            record('Mathematics and Physics BSc', 'joint', [
                'Subject area: Mathematics (sa26)', 'Subject area: Physics (sa32)']),
            record('Mathematics and Physics BSc', 'joint'),
            record('Hidden placeholder', 'hidden', ['Visibility: Hidden']),
        ]}
        snapshot, report = build_snapshot(feed, {'items': []})
        self.assertEqual([c['name'] for c in snapshot['items']], ['Mathematics and Physics BSc', 'Zoology BSc'])
        self.assertEqual(snapshot['items'][0]['subject_ids'], ['mathematics', 'physics'])
        self.assertEqual(report['courses'], 2)
        self.assertEqual(report['unclassified_ids'], ['zoology'])
        self.assertFalse(snapshot['curated'])

    def test_previous_ids_urls_and_primary_subject_preserved(self):
        previous = {'items': [{'id': 'legacy-id', 'name': 'Old name', 'subject': 'computing',
                              'source_url': 'https://warwick.ac.uk/study/undergraduate/courses/course/'}]}
        snapshot, _ = build_snapshot({'items': [record('Computer Science BSc', 'course', anchor='new-anchor')]}, previous)
        self.assertEqual(snapshot['items'][0]['id'], 'legacy-id')
        self.assertEqual(snapshot['items'][0]['source_url'], previous['items'][0]['source_url'])
        self.assertEqual(snapshot['items'][0]['subject'], 'computing')

    def test_duplicate_ids_missing_old_courses_and_malformed_records_rejected(self):
        for feed in [{'items': []}, {'items': [None]}, {'items': [{'title': 'Missing link'}]},
                     {'items': [record('One', 'one', anchor='same'), record('Two', 'two', anchor='same')]}]:
            with self.subTest(feed=feed), self.assertRaises(ValueError):
                build_snapshot(feed, {'items': []})
        old = {'items': [{'id': 'old', 'source_url': 'https://warwick.ac.uk/study/undergraduate/courses/old'}]}
        with self.assertRaises(ValueError):
            build_snapshot({'items': [record('New course', 'new')]}, old)

    def test_refresh_failure_preserves_snapshot_and_valid_refresh_is_atomic(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'courses.json'
            path.write_text('{"items": []}', encoding='utf-8')
            original = path.read_bytes()
            with self.assertRaises(ValueError):
                refresh(path, {'items': [{'title': 'Invalid'}]})
            self.assertEqual(path.read_bytes(), original)
            with patch('BACKEND.refresh_courses.urlopen', side_effect=OSError('offline')):
                with self.assertRaises(OSError):
                    refresh(path)
            self.assertEqual(path.read_bytes(), original)
            feed = {'items': [record('Computer Science BSc', 'computing')]}
            with patch('BACKEND.refresh_courses.os.replace', side_effect=OSError('locked')):
                with self.assertRaises(OSError):
                    refresh(path, feed)
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(list(Path(folder).glob('*.tmp')), [])
            refresh(path, feed)
            self.assertEqual(json.loads(path.read_text())['items'][0]['subject_ids'], ['computing'])

    def test_bundled_snapshot_is_complete_sorted_and_unique(self):
        from BACKEND.onboarding import CATALOGS
        items = CATALOGS['courses']['items']
        self.assertGreater(len(items), 100)
        self.assertEqual(items, sorted(items, key=lambda c: (c['name'].casefold(), c['id'])))
        self.assertEqual(len(items), len({c['id'] for c in items}))
        self.assertEqual(len(items), len({c['source_url'].rstrip('/') for c in items}))
        joint = next(c for c in items if c['id'] == 'mathematics-and-statistics-bsc')
        self.assertEqual(joint['subject_ids'], ['mathematics', 'statistics'])
