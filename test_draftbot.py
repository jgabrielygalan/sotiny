import unittest
from booster import Booster
from draft_player import DraftPlayer
from draftbot import DraftBot
import pytest

@pytest.fixture()
def player() -> DraftPlayer:
    return DraftPlayer(1, 1)

@pytest.fixture()
def bot(player: DraftPlayer) -> DraftBot:
    return DraftBot(player)

@pytest.mark.asyncio
async def test_no_pack(bot):
    pick = await bot.pick()
    assert pick is None

@pytest.mark.vcr(record_mode='new_episodes')
@pytest.mark.asyncio
async def test_force_red(player: DraftPlayer, bot: DraftBot):
    player.deck.extend(["Lightning Bolt", "Shock", "Goblin Guide", "Ponder"])
    booster = Booster(['As Foretold', 'Blood Moon', 'Choke'], 1)
    player.push_pack(booster)
    pick = await bot.pick()
    assert pick == "Blood Moon"
