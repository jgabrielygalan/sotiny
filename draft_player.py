from typing import List, Optional, Set

from booster import Booster


class DraftPlayer:
    def __init__(self, id: int, next: int, previous: int):
        self.id = id
        self.next = next
        self.previous = previous
        self.queue: List[Booster] = []
        self.deck: List[str] = []
        self.face_up: List[str] = []
        self.current_pack: Optional[Booster] = None
        self.booster_number = 0

    def __str__(self) -> str:
        return str(self.id)

    def __repr__(self):
        return self.id.__repr__()

    def push_pack(self, booster: Booster, front_of_queue: bool = False) -> bool:
        if self.current_pack is None:
            self.current_pack = booster
            return True # review interface
        elif front_of_queue:
            self.queue.insert(0, booster)
            return False
        else:
            self.queue.append(booster)
            return False

    def pick(self, position: int):
        if self.current_pack is None:
            return None
        card = self.current_pack.pick_by_position(position)
        if card is None:
            return None
        self.deck.append(card)
        current_pack = self.current_pack
        self.current_pack = None
        if len(self.queue) > 0:
            self.current_pack = self.queue.pop(0)
        return current_pack

    def autopick(self):
        return self.pick(1)

    def last_pick(self):
        return self.deck[-1]

    def has_current_pack(self):
        return self.current_pack is not None

    def has_queued_packs(self):
        return len(self.queue) > 0

    def has_one_card_in_current_pack(self):
        return self.has_current_pack() and self.current_pack.number_of_cards() == 1
