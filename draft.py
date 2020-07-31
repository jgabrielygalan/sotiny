import random
from booster import Booster
from draft_player import DraftPlayer
from enum import Enum
from typing import Any, Dict, List, Optional
from cog_exceptions import UserFeedbackException
import utils


PickReturn = Enum('PickReturn', 'pick_error, in_progress, next_booster, finished, next_booster_autopick')


class Draft:
    """
    The internals of a draft.  This represents the abstract state of the draft.
    This is where all the logic of a Booster Draft happens.
    """
    def __init__(self, players: List[int], card_list: List[str]) -> None:
        self.cards = card_list
        self.players = players
        random.shuffle(self.players)
        self.state = {}
        self.opened_packs = 0
        for i, player in enumerate(players):
            self.state[player] = DraftPlayer(player, players[(i+1)%len(players)], players[i-1])

    def pack_of(self, player_id: int) -> Booster:
        return self.state[player_id].current_pack

    def deck_of(self, player_id: int) -> List[str]:
        return self.state[player_id].deck

    def start(self, number_of_packs: int, cards_per_booster: int, cube: None = None) -> PickReturn:
        if number_of_packs * cards_per_booster * len(self.players) > len(self.cards):
            raise UserFeedbackException(f"Not enough cards {len(self.cards)} for {len(self.players)} with {number_of_packs} of {cards_per_booster}")
        self.number_of_packs = number_of_packs
        self.cards_per_booster = cards_per_booster
        random.shuffle(self.cards)
        self.open_boosters_for_all_players()
        return self.state.values() # return all players to update

    def open_booster(self, player: DraftPlayer, number: int) -> Booster:
        card_list = [self.cards.pop() for _ in range(0,self.cards_per_booster)]
        booster = Booster(card_list, number)
        player.push_pack(booster)

    def open_boosters_for_all_players(self) -> None:
        self.opened_packs += 1
        for player in self.state.values():
            self.open_booster(player, self.opened_packs)
        print("Opening pack for all players")

    def get_pending_players(self):
        return [x for x in self.state.values() if x.has_current_pack()]

    def is_draft_finished(self):
        return (self.is_pack_finished() and (self.opened_packs >= self.number_of_packs))

    def is_pack_finished(self):
        return len(self.get_pending_players()) == 0

    def pick(self, player_id: int, position: int) -> List[Dict[str, Any]]:
        users_to_update = []
        player = self.state[player_id]
        pack = player.pick(position)
        if pack is None:
            return users_to_update

        print(f"Player {player_id} picked {player.last_pick()}")

        # push to next player
        if not was_last_pick_of_pack(pack):
            next_player_id = get_next_player(player, pack)
            next_player = self.state[next_player_id]
            has_new_pack = next_player.push_pack(pack)
            if has_new_pack:
                users_to_update.append(next_player)
        
        if player.has_current_pack() and player not in users_to_update:
            users_to_update.append(player)

        result = []
        for player in users_to_update:
            updates = {'player': player, 'autopicks': []}
            if player.has_one_card_in_current_pack():
                self.autopick(player)
                updates['autopicks'].append(player.last_pick())
            result.append(updates)

        if self.is_draft_finished():
            print("Draft finished")

        return result

    def autopick(self, player: DraftPlayer):
        if player.has_one_card_in_current_pack():
            pack = player.autopick()
            if self.is_pack_finished() and not self.is_draft_finished():
                self.open_boosters_for_all_players()


def get_next_player(player: DraftPlayer, pack: Booster):
    if pack.number % 2 == 1:
        return player.next
    return player.previous

def was_last_pick_of_pack(pack: Booster):
    return pack.is_empty()
