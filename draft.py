import random
from booster import Booster
from draft_player import DraftPlayer
from enum import Enum
from typing import List, Optional
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
        for i, player in enumerate(players):
            self.state[player] = DraftPlayer(player, players[(i+1)%len(players)], players[i-1])

    def pack_of(self, player_id: int) -> Booster:
        return self.state[player_id].current_pack

    def deck_of(self, player_id: int) -> List[str]:
        return self.state[player_id].deck

    def start(self, number_of_packs: int, cards_per_booster: int, cube: None = None) -> PickReturn:
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
        for player in self.state.values():
            self.open_booster(player, 1)
        print("Opening pack 1 for all players")

    def get_pending_players(self):
        return [x for x in self.state.values() if x.has_current_pack()]

    def is_draft_finished(self):
        return len(self.get_pending_players()) == 0

    def pick(self, player_id: int, position: int):
        users_to_update = []
        player = self.state[player_id]
        pack = player.pick(position)
        if pack is None:
            return users_to_update

        print(f"Player {player_id} picked {player.last_pick()}")
        final_pack = pack
        if just_one_card_in_current_pack(player):
            # Autopick
            final_pack = player.autopick()

        if was_last_pick_of_pack(final_pack):
            if self.number_of_packs > pack.number:
                self.open_booster(player, pack.number + 1)
        else:
            next_player_id = get_next_player(player, pack)
            next_player = self.state[next_player_id]
            is_current = next_player.push_pack(pack)
            if is_current:
                users_to_update.append(next_player)


        if player.has_current_pack() and player not in users_to_update:
            users_to_update.append(player)

        if self.is_draft_finished():
            print("Draft finished")

        return users_to_update

    def autopick(self) -> PickReturn:
        if len(self.state[self.players[0]].cards) != 1:
            print(f"Error, can't autopick. Pack is: {self.state[self.players[0]].cards}")
            return PickReturn.pick_error
        for player in self.players:
            state = self.pick(player, position=0)
        return state

def get_next_player(player: DraftPlayer, pack: Booster):
    if pack.number % 2 == 1:
        return player.next
    return player.previous

def was_last_pick_of_pack(pack: Booster):
    return pack.is_empty()

def just_one_card_in_current_pack(player: DraftPlayer):
    return player.has_current_pack() and player.current_pack.number_of_cards() == 1