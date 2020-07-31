import unittest
from booster import Booster

class TestBooster(unittest.TestCase):

    def test_booster_number(self):
        booster = Booster(['a', 'b', 'c'], 1)
        self.assertEqual(1, booster.number)

    def test_number_of_cards(self):
        booster = Booster(['a', 'b', 'c'], 1)
        self.assertEqual(3, booster.number_of_cards())

    def test_is_empty(self):
        booster = Booster([], 1)
        self.assertTrue(booster.is_empty())

    def test_is_not_empty(self):
        booster = Booster(['a'], 1)
        self.assertFalse(booster.is_empty())

    def test_pick_wrong_card(self):
        booster = Booster(['a'], 1)
        result = booster.pick_by_position(3)
        self.assertIsNone(result)

    def test_first_card(self):
        booster = Booster(['a', 'b', 'c'], 1)
        result = booster.pick_by_position(1)
        self.assertEqual('a', result)
        self.assertEqual(2, booster.number_of_cards())
        self.assertEqual(['b', 'c'], booster.cards)

    def test_last_card(self):
        booster = Booster(['a', 'b', 'c'], 1)
        result = booster.pick_by_position(3)
        self.assertEqual('c', result)
        self.assertEqual(2, booster.number_of_cards())
        self.assertEqual(['a', 'b'], booster.cards)

    def test_middle_card(self):
        booster = Booster(['a', 'b', 'c'], 1)
        result = booster.pick_by_position(2)
        self.assertEqual('b', result)
        self.assertEqual(2, booster.number_of_cards())
        self.assertEqual(['a', 'c'], booster.cards)

    def test_pick_from_empty(self):
        booster = Booster([], 1)
        result = booster.pick_by_position(1)
        self.assertIsNone(result)

