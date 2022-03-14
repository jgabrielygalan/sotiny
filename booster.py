from typing import List, Optional

import attr


@attr.s(auto_attribs=True)
class Booster(object):
    cards: List[str]
    number: int
    pick_number: int = 1

    def is_empty(self) -> bool:
        return self.number_of_cards() == 0

    def number_of_cards(self) -> int:
        return len(self.cards)

    def pick_by_position(self, position: int) -> Optional[str]:
        if position <= 0 or len(self.cards) < position:
            return None
        self.pick_number += 1
        return self.cards.pop(position-1)
