import unittest

from core_draft.booster import Booster
from core_draft.draft_player import DraftPlayer


class TestDraftPlayer(unittest.TestCase):
    def setUp(self):
        self.player = DraftPlayer(1, 1)

    def add_a_pack(self, cards = None, number = 1):
        if cards is None:
            cards = ['a', 'b', 'c']
        booster = Booster(cards, number)
        self.player.push_pack(booster)
        return booster

    def test_id(self):
        self.assertEqual(1, self.player.id)

    def test_no_current_pack_at_start(self):
        self.assertFalse(self.player.has_current_pack())

    def test_has_current_pack(self):
        self.add_a_pack()
        self.assertTrue(self.player.has_current_pack())

    def test_push_pack_with_no_current(self):
        booster = Booster(['a', 'b', 'c'], 1)
        result = self.player.push_pack(booster)
        self.assertTrue(result)
        self.assertTrue(self.player.has_current_pack())
        self.assertEqual(booster, self.player.current_pack)
        self.assertFalse(self.player.has_queued_packs())

    def test_push_pack_with_current(self):
        booster = Booster(['a', 'b', 'c'], 1)
        self.player.push_pack(booster)

        booster2 = Booster(['d', 'e', 'f'], 1)
        result = self.player.push_pack(booster2)

        self.assertFalse(result)
        self.assertTrue(self.player.has_current_pack())
        self.assertEqual(booster, self.player.current_pack)
        self.assertNotEqual(booster2, self.player.current_pack)
        self.assertTrue(self.player.has_queued_packs())

    def test_pick_with_no_current(self):
        result = self.player.pick(1)
        self.assertIsNone(result)
        self.assertFalse(self.player.has_current_pack())

    def test_pick_wrong_position(self):
        booster = self.add_a_pack()
        result = self.player.pick(7)
        self.assertIsNone(result)
        self.assertEqual(booster, self.player.current_pack)

    def test_pick_no_queue(self):
        booster = self.add_a_pack()
        result = self.player.pick(1)
        self.assertEqual(booster, result)
        self.assertEqual('a', self.player.deck[0])
        self.assertEqual(2, booster.number_of_cards())
        self.assertFalse(self.player.has_current_pack())

    def test_pick_queue(self):
        booster1 = self.add_a_pack()
        booster2 = self.add_a_pack(['d', 'e', 'f'], 2)
        result = self.player.pick(1)
        self.assertEqual(booster1, result)
        self.assertTrue(self.player.has_current_pack())
        self.assertEqual(booster2, self.player.current_pack)

    def test_autopick(self):
        booster1 = self.add_a_pack()
        result = self.player.autopick()
        self.assertEqual(booster1, result)
        self.assertEqual('a', self.player.deck[0])
        self.assertEqual(2, booster1.number_of_cards())

    def test_lastpick(self):
        self.player = DraftPlayer(1, 1)
        self.add_a_pack()
        self.player.pick(1)
        self.assertEqual('a', self.player.last_pick())

    def test_no_queued_packs(self):
        self.assertFalse(self.player.has_queued_packs())

    def test_a_single_pack_is_not_queued(self):
        self.add_a_pack()
        self.assertFalse(self.player.has_queued_packs())

    def test_queued_pack(self):
        self.add_a_pack()
        self.add_a_pack(['d', 'e', 'f'], 2)
        self.assertTrue(self.player.has_queued_packs())
