from typing import List, Optional, Set

import attr

from booster import Booster


@attr.s(auto_attribs=True, hash=False)
class DraftPlayer:
    id: int
    seat: int
    queue: List[Booster] = attr.ib(factory=list)
    deck: List[str] = attr.ib(factory=list)
    face_up: List[str] = attr.ib(factory=list)
    current_pack: Optional[Booster] = None

    def __init__(self, id: int, seat: int) -> None:
        self.id = id
        self.seat = seat

    def __hash__(self) -> int:
        return id.__hash__()

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
