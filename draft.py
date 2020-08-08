import random
from booster import Booster
from draft_player import DraftPlayer
from enum import Enum
from typing import Any, Dict, List, Optional, Iterable, Tuple
from cog_exceptions import UserFeedbackException
import attr

DraftEffect = Enum('DraftEffect', 'no_immediate_effect add_booster_to_draft')

player_card_drafteffect = Tuple[DraftPlayer, str, DraftEffect]

CARDS_WITH_FUNCTION = ["Cogwork Librarian", "Leovold's Operative"]

@attr.s(auto_attribs=True)
class PickReturn():
    updates: List[Dict[str, Any]]
    draft_effect: List[player_card_drafteffect]

class Draft:
    """
    The internals of a draft.  This represents the abstract state of the draft.
    This is where all the logic of a Booster Draft happens.
    """
    def __init__(self, players: List[int], card_list: List[str]) -> None:
        self.cards = card_list
        self.players = players
        random.shuffle(self.players)
        self.state: Dict[int, DraftPlayer] = {}
        self.opened_packs = 0
        for i, player in enumerate(players):
            self.state[player] = DraftPlayer(player, players[(i+1)%len(players)], players[i-1])

    def player_by_id(self, player_id: int) -> DraftPlayer:
        return self.state[player_id]

    def pack_of(self, player_id: int) -> Booster:
        return self.state[player_id].current_pack

    def deck_of(self, player_id: int) -> List[str]:
        return self.state[player_id].deck

    def start(self, number_of_packs: int, cards_per_booster: int, cube: None = None) -> Iterable[DraftPlayer]:
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
        player.push_pack(booster, True)
        return booster

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

    def pick(self, player_id: int, position: int) -> PickReturn:
        player = self.state[player_id]
        pack = player.pick(position)
        if pack is None:
            return PickReturn([], [])

        users_to_update: List[DraftPlayer] = []

        pick = player.last_pick()
        print(f"Player {player_id} picked {pick}")

        pick_effects = []
        effect = self.check_if_draft_matters(player, pack)
        if effect:
            player.face_up.append(pick)
            pick_effects.append(effect)

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
        new_booster = False
        for player in users_to_update:
            updates = {'player': player, 'autopicks': []}
            if player.has_one_card_in_current_pack():
                new_booster, effect = self.autopick(player)
                if effect:
                    player.face_up.append(player.last_pick())
                    pick_effects.append(effect)
                updates['autopicks'].append(player.last_pick())

            result.append(updates)

        if new_booster:
            for player in self.state.values():
                if player not in users_to_update:
                    result.append({'player': player, 'autopicks': []})

        if self.is_draft_finished():
            print("Draft finished")

        return PickReturn(result, pick_effects)

    def check_if_draft_matters(self, player: DraftPlayer, pack: Booster) -> Optional[player_card_drafteffect]:
        pick = player.last_pick()
        if pick == 'Lore Seeker': # Reveal Lore Seeker as you draft it. After you draft Lore Seeker, you may add a booster pack to the draft
            self.open_booster(player, pack.number)
            return (player, pick, DraftEffect.add_booster_to_draft)
        if pick in ['Cogwork Librarian', "Leovold's Operative"]:
            return (player, pick, DraftEffect.no_immediate_effect)

        return None

    def autopick(self, player: DraftPlayer) -> Tuple[bool, Optional[player_card_drafteffect]]:
        if player.has_one_card_in_current_pack():
            pack = player.autopick()
            pick_effect = self.check_if_draft_matters(player, pack)
            nextbooster = False
            if self.is_pack_finished() and not self.is_draft_finished():
                self.open_boosters_for_all_players()
                nextbooster = True
            return nextbooster, pick_effect
        return False, None


def get_next_player(player: DraftPlayer, pack: Booster):
    if pack.number % 2 == 1:
        return player.next
    return player.previous

def was_last_pick_of_pack(pack: Booster):
    return pack.is_empty()
