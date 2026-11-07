import unittest
from BACKEND.relevance import terms_for, relevance


class RelevanceTests(unittest.TestCase):
    def test_travel_expands_and_ranks_direct_matches_first(self):
        direct, related = terms_for('travel')
        scores = {title: relevance({'title': title}, direct, related)[0] for title in [
            'travel adventures', 'Warwick Darts Battle Bus to Gloucester', 'LOST 2026', 'pottery workshop']}
        self.assertGreater(scores['travel adventures'], scores['Warwick Darts Battle Bus to Gloucester'])
        self.assertGreater(scores['Warwick Darts Battle Bus to Gloucester'], 0)
        self.assertGreater(scores['LOST 2026'], 0)
        self.assertEqual(scores['pottery workshop'], 0)

    def test_constraint_only_request_has_no_topic(self):
        self.assertEqual(terms_for('find free food tomorrow without clashes'), (set(), set()))

    def test_related_concepts_and_word_boundaries(self):
        direct, related = terms_for('music')
        self.assertGreater(relevance({'title': 'jazz concert'}, direct, related)[0], 0)
        direct, related = terms_for('travel')
        self.assertEqual(relevance({'title': 'business workshop'}, direct, related)[0], 0)
