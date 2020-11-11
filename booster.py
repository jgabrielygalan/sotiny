from typing import List

import attr


@attr.s(auto_attribs=True)
class Booster(object):
    cards: List[str]
    number: int
    pick_number = 1

    def is_empty(self):
        return self.number_of_cards() == 0

    def number_of_cards(self):
        return len(self.cards)

    def pick_by_position(self, position: int) -> str:
        if position <= 0 or len(self.cards) < position:
            return None
        self.pick_number += 1
        return self.cards.pop(position-1)
