"""Student profiles are separate from existing plans and private to each session."""
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import FastAPI
from fastapi.testclient import TestClient

from BACKEND.onboarding import (COURSES, INTEREST_CATEGORIES, SOCIETIES,
                                StudentProfile, matching_societies, resolve_society_name)
from BACKEND.workflow import create_workflow
from shared.schema import Event


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
        sample = Event(id='seed-event', title='Sample', society='Computing', category='academic',
                       start=datetime(2090, 1, 1, tzinfo=ZoneInfo('Europe/London')),
                       confidence=1, needs_review=False)
        earlier = sample.model_copy(update={'id': 'earlier-event', 'title': 'Earlier event',
                                           'start': datetime(2089, 1, 1, tzinfo=ZoneInfo('Europe/London'))})
        app.include_router(create_workflow(self.path, event_provider=lambda: [sample, earlier]), prefix='/api')
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
            self.assertEqual(catalog['curated'], name != 'courses')
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

    def test_recommendation_context_has_current_signals_without_demographics(self):
        self.put({'course_id': 'mathematics-and-physics-bsc', 'graduation_year': self.year + 2,
                  'interest_ids': ['programming'], 'followed_society_ids': [self.society],
                  'ethnicity': 'Private description', 'cultural_recommendations_opt_in': True})
        response = self.client.put('/api/plans', headers=self.headers, json={
            'liked': ['imported:seed-event'], 'signed': ['imported:seed-event'], 'interests': []})
        self.assertEqual(response.status_code, 200)
        context = self.get('/recommendation-context').json()
        self.assertEqual(context['version'], 1)
        self.assertEqual(context['course_subject_ids'], ['mathematics', 'physics'])
        self.assertEqual(context['event_categories'], ['academic'])
        self.assertEqual(context['liked_event_ids'], ['imported:seed-event'])
        self.assertEqual(context['signed_event_ids'], ['imported:seed-event'])
        self.assertEqual(context['followed_societies'][0]['id'], self.society)
        self.assertNotIn('ethnicity', context)
        self.assertNotIn('cultural_recommendations_opt_in', context)
        self.assertNotIn('Private description', str(context))
        self.put({'interest_ids': [], 'followed_society_ids': [], 'course_id': 'not-listed'})
        context = self.get('/recommendation-context').json()
        self.assertEqual(context['course_subject_ids'], [])
        self.assertEqual(context['event_categories'], [])
        self.assertEqual(context['followed_societies'], [])
        self.assertEqual(context['liked_event_ids'], ['imported:seed-event'])
        self.assertEqual(self.client.get('/api/recommendation-context').status_code, 401)
        other = self.login('other-context@example.com')
        self.assertEqual(self.get('/recommendation-context', other).json()['liked_event_ids'], [])
        for role in ['exec', 'external']:
            headers = self.login(role + '-context@example.com', role)
            self.assertEqual(self.get('/recommendation-context', headers).status_code, 403)

    def test_joint_subject_matching_and_explicit_society_aliases(self):
        profile = StudentProfile(course_id='mathematics-and-physics-bsc')
        matches = matching_societies(profile)
        self.assertTrue(any(s['name'] == 'Physics Society' for s in matches))
        self.assertTrue(any(s['name'] == 'Warwick Maths Society' for s in matches))
        # One course point even if more than one mapped subject overlaps.
        self.assertTrue(all(s['score'] == 1 for s in matches))
        self.assertEqual(resolve_society_name('  COMPUTING '), self.society)
        self.assertIsNone(resolve_society_name('Some unrelated society'))
        ambiguous = [{'id': 'one', 'name': 'One', 'event_name_aliases': ['shared']},
                     {'id': 'two', 'name': 'Two', 'event_name_aliases': ['shared']}]
        self.assertIsNone(resolve_society_name('Shared', ambiguous))

    def test_preference_data_does_not_reorder_the_catalog(self):
        before = self.get('/catalog').json()
        self.assertEqual([e['id'] for e in before], ['imported:earlier-event', 'imported:seed-event'])
        self.put({'course_id': self.course, 'interest_ids': ['programming'],
                  'followed_society_ids': [self.society]})
        self.get('/recommendation-context')
        self.assertEqual(self.get('/catalog').json(), before)
