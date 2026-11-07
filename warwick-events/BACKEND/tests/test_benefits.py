import unittest
from BACKEND.benefits import event_benefits


class BenefitsTests(unittest.TestCase):
    def test_food_does_not_imply_free_admission(self):
        event = event_benefits({'title': 'ticketed social', 'description': 'free pizza provided'})
        self.assertTrue(event['freeFood'])
        self.assertFalse(event['freeEntry'])

    def test_free_admission_does_not_imply_food(self):
        event = event_benefits({'title': 'free entry concert'})
        self.assertTrue(event['freeEntry'])
        self.assertFalse(event['freeFood'])

    def test_uncertain_food_is_labelled_and_unknown_prices_stay_unknown(self):
        self.assertTrue(event_benefits({'title': 'Langar on Campus'})['likelyFreeFood'])
        for title in ['Pepero Stick Making', 'Arayes Masterclasss', 'Film Night']:
            event = event_benefits({'title': title})
            self.assertFalse(event['freeFood'])
            self.assertFalse(event['freeEntry'])

    def test_negation_and_organiser_flags(self):
        self.assertFalse(event_benefits({'description': 'no free pizza; not free entry'})['freeFood'])
        self.assertFalse(event_benefits({'description': 'no free pizza; not free entry'})['freeEntry'])
        event = event_benefits({'freeFood': True, 'freeEntry': True})
        self.assertTrue(event['freeFood'])
        self.assertTrue(event['freeEntry'])
