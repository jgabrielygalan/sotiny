from typing import Optional

import attrs
import numpy

from core_draft.cube import Card, fetch_card
from core_draft.draft_player import DraftPlayer

DECK_CACHE: dict[str, list[str]] = {}

@attrs.define()
class DraftBot:
    player: DraftPlayer

    async def pick(self) -> Optional[str]:
        return await self.force()

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
            if not card.colors:
                card.colors = []
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
            if not card.colors:
                card.colors = []
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
        return cards[0].name
