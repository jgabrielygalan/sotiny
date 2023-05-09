import attrs
from typing import Protocol

from core_draft.booster import Booster

class CardGenerator(Protocol):
    def generate_boster(self, number: int) -> Booster:
        ...

@attrs.define()
class CubeCardGenerator(CardGenerator):
    cards: list[str] = attrs.field(repr=lambda cl: f'[{len(cl)} cards]')
    cards_per_booster: int

    def generate_booster(self, number: int) -> Booster:
        card_list = [self.cards.pop() for _ in range(0, self.cards_per_booster)]
        booster = Booster(card_list, number)
        return booster
