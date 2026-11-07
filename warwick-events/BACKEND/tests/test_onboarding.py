"""Student profiles are separate from existing plans and private to each session."""
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import FastAPI
from fastapi.testclient import TestClient

from BACKEND.onboarding import COURSES, INTEREST_CATEGORIES, SOCIETIES
from BACKEND.workflow import create_workflow


class OnboardingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'workflow.sqlite3'
        self.client = self.new_client()
        self.headers = self.login('student@example.com')
        self.year = datetime.now(ZoneInfo('Europe/London')).year
        self.course = next(c['id'] for c in COURSES.values() if c['subject'] == 'computing')
        self.society = next(s['id'] for s in SOCIETIES.values() if s['name'] == 'Computing')

    def new_client(self):
        app = FastAPI()
        app.include_router(create_workflow(self.path), prefix='/api')
        return self.enterContext(TestClient(app))

    def login(self, email, role='student'):
        response = self.client.post('/api/session', json={'email': email, 'role': role})
        return {'Authorization': 'Bearer ' + response.json()['token']}

    def get(self, path='/profile', headers=None):
        return self.client.get('/api' + path, headers=headers or self.headers)

    def put(self, body, headers=None):
        return self.client.put('/api/profile', headers=headers or self.headers, json=body)

    def test_first_profile_and_completed_returning_student(self):
        profile = self.get().json()
        self.assertFalse(profile['onboarding_completed'])
        self.assertIsNone(profile['ethnicity'])
        self.assertFalse(self.get('/state').json()['onboarding_completed'])
        self.assertEqual(self.put({'onboarding_completed': True}).status_code, 422)
        response = self.put({'course_id': self.course, 'graduation_year': self.year + 2,
                             'step': 4, 'onboarding_completed': True})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.get('/state').json()['onboarding_completed'])
        # A new login with the same demo email retains completion.
        self.headers = self.login('student@example.com')
        self.assertTrue(self.get().json()['onboarding_completed'])

    def test_partial_updates_deduplication_and_clear_ethnicity(self):
        response = self.put({'interest_ids': ['programming', 'programming'],
                             'ethnicity': 'Self description', 'step': 2})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['interest_ids'], ['programming'])
        self.assertEqual(response.json()['event_categories'], ['academic'])
        self.assertFalse(response.json()['cultural_recommendations_opt_in'])
        response = self.put({'ethnicity': None, 'followed_society_ids': [self.society, self.society]})
        self.assertEqual(response.json()['interest_ids'], ['programming'])
        self.assertIsNone(response.json()['ethnicity'])
        self.assertEqual(response.json()['followed_society_ids'], [self.society])
        self.assertEqual(self.put({'followed_society_ids': [], 'interest_ids': []}).status_code, 200)
        self.assertEqual(self.get().json()['followed_society_ids'], [])

    def test_validation(self):
        for body in [{'course_id': 'invented'}, {'graduation_year': self.year - 1},
                     {'graduation_year': self.year + 11}, {'graduation_year': '2028'},
                     {'interest_ids': ['invented']}, {'followed_society_ids': ['invented']},
                     {'step': 5}, {'user_id': 'someone-else'}, {'interest_ids': None},
                     {'ethnicity': 'x' * 101}]:
            with self.subTest(body=body):
                self.assertEqual(self.put(body).status_code, 422)
        self.assertEqual(self.put({'course_id': 'not-listed', 'graduation_year': self.year,
                                  'onboarding_completed': True}).status_code, 200)

    def test_isolation_roles_and_catalog_authentication(self):
        self.put({'ethnicity': 'Private', 'interest_ids': ['programming']})
        other = self.login('other@example.com')
        self.assertEqual(self.get(headers=other).json()['interest_ids'], [])
        self.assertNotIn('Private', self.get('/state').text)
        self.assertNotIn('Private', self.get('/societies/matches').text)
        for role in ['exec', 'external']:
            headers = self.login(role + '@example.com', role)
            self.assertEqual(self.get(headers=headers).status_code, 403)
            self.assertEqual(self.put({}, headers).status_code, 403)
            self.assertEqual(self.get('/societies/matches', headers).status_code, 403)
            self.assertTrue(self.get('/state', headers).json()['onboarding_completed'])
        for path in ['/profile', '/courses', '/interests', '/societies', '/societies/matches']:
            self.assertEqual(self.client.get('/api' + path).status_code, 401)

    def test_catalogs_and_matching(self):
        self.assertEqual(self.get('/societies/matches').json(), [])
        for name in ['courses', 'interests', 'societies']:
            catalog = self.get('/' + name).json()
            self.assertTrue(catalog['curated'])
            self.assertTrue(catalog['source_url'].startswith('https://'))
            self.assertTrue(catalog['items'])
        for society in SOCIETIES.values():
            self.assertTrue(set(society['interest_ids']).issubset(INTEREST_CATEGORIES))
        self.put({'course_id': self.course, 'interest_ids': ['programming'],
                  'followed_society_ids': [self.society]})
        matches = self.get('/societies/matches').json()
        computing = next(s for s in matches if s['id'] == self.society)
        self.assertEqual(computing['score'], 3)
        self.assertTrue(computing['followed'])
        self.assertEqual(computing['matching_interest_ids'], ['programming'])
        expected = sorted(matches, key=lambda item: (-item['score'], item['name'].casefold(), item['id']))
        self.assertEqual(matches, expected)
        self.put({'ethnicity': 'Different', 'cultural_recommendations_opt_in': True})
        self.assertEqual(self.get('/societies/matches').json(), matches)

    def test_persistence_and_plans_do_not_overwrite_profile(self):
        self.put({'interest_ids': ['gaming'], 'step': 3})
        response = self.client.put('/api/plans', headers=self.headers,
                                   json={'liked': [], 'signed': [], 'interests': ['sports']})
        self.assertEqual(response.status_code, 200)
        self.put({'course_id': self.course})
        self.assertEqual(self.get('/state').json()['plans']['interests'], ['sports'])
        restarted = self.new_client()
        persisted = restarted.get('/api/profile', headers=self.headers).json()
        self.assertEqual(persisted['interest_ids'], ['gaming'])
        self.assertEqual(persisted['step'], 3)
