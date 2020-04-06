from typing import List


class Booster(object):
    def __init__(self, cards: List[str], number: int) -> None:
        super(Booster, self).__init__()
        self.cards = cards
        self.number = number
        self.pick_number = 1

    def __str__(self) -> str:
        return ", ".join(self.cards)
		
    def __repr__(self):
        return self.cards.__repr__()

    def is_empty(self):
        return self.number_of_cards() == 0

    def number_of_cards(self):
        return len(self.cards)

    def pick_by_position(self, position: int) -> str:
        if position <= 0 or len(self.cards) < position:
            return None
        self.pick_number += 1
        return self.cards.pop(position-1)
