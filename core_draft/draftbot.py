import os
from typing import Optional

import attrs
import numpy

from core_draft.cube import Card, fetch_card, CARD_INFO
from core_draft.draft_player import DraftPlayer

DECK_CACHE: dict[str, list[str]] = {}

@attrs.define()
class DraftBot:
    player: DraftPlayer

    async def pick(self) -> Optional[str]:
        card = await self.score()
        if card:
            return card
        return await self.force()

    async def score(self) -> Optional[str]:
        pack = self.player.current_pack
        if pack is None:
            return None

        if not DECK_CACHE:
            load_decks()

        decks = list(DECK_CACHE.values())
        scores = {c: 0.0 for c in pack.cards}
        for card in pack.cards:
            for deck in decks:
                if card in deck:
                    scores[card] += similarity_score(deck, self.player.deck)

        # todo: finish this
        return None

    async def force(self) -> Optional[str]:
        """
        Forces a colour.  Not the smartest, but it does the job.
        """
        pack = self.player.current_pack
        if pack is None:
            return None
        wubrg = numpy.array([0, 0, 0, 0, 0])
        deck: list[Card] = [await fetch_card(c) for c in self.player.deck]
        for card in deck:
            if card.details.colors is None:
                card.details.colors = []
            wubrg += numpy.array(
                [
                    "W" in card.colors,
                    "U" in card.colors,
                    "B" in card.colors,
                    "R" in card.colors,
                    "G" in card.colors,
                ]
            )

        def weight(card: Card) -> int:
            w = 0
            if card.details.colors is None:
                card.details.colors = []
            if "W" in card.colors:
                w += wubrg[0]
            if "U" in card.colors:
                w += wubrg[1]
            if "B" in card.colors:
                w += wubrg[2]
            if "R" in card.colors:
                w += wubrg[3]
            if "G" in card.colors:
                w += wubrg[4]
            return w

        cards = [await fetch_card(c) for c in pack.cards]
        cards.sort(key=weight, reverse=True)
        name = cards[0].name
        if name not in pack.cards:
            names = {(await fetch_card(c)).name: c for c in pack.cards}
            name = names[name]
        return name


def similarity_score(a: list[str], b: list[str]) -> float:
    score = 0
    for c in a:
        if c in b:
            score += 1
    return float(score) / float(max(len(a), len(b)))

def load_decks() -> None:
    for d in os.listdir('decks'):
        with open(f'decks/{d}') as f:
            cards = [line.strip() for line in f.readlines() if line and not line.isspace()]
            DECK_CACHE[d] = cards
