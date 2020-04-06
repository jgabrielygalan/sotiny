import unittest
from draft_player import DraftPlayer
from booster import Booster

class TestDraftPlayer(unittest.TestCase):
    def setUp(self):
        self.player = DraftPlayer(1, 2, 3)

    def test_id(self):        
        self.assertEqual(1, self.player.id)

    def test_next(self):        
        self.assertEqual(2, self.player.next)

    def test_previous(self):        
        self.assertEqual(3, self.player.previous)

    def test_no_current_pack_at_start(self):
        self.assertFalse(self.player.has_current_pack())

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
