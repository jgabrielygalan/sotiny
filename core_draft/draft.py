import random
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import attr

from core_draft.booster import Booster
from core_draft.cog_exceptions import UserFeedbackException
from core_draft.draft_player import DraftPlayer

DraftEffect = Enum('DraftEffect', 'no_immediate_effect add_booster_to_draft')
Stage = Enum('Stage', 'draft_registration draft_in_progress draft_complete')

player_card_drafteffect = Tuple[DraftPlayer, str, DraftEffect]

CARDS_WITH_FUNCTION = {"Cogwork Librarian", "Leovold's Operative"}

@attr.s(auto_attribs=True)
class PickReturn():
    updates: Dict[DraftPlayer, List[str]]
    draft_effect: List[player_card_drafteffect]

@attr.s(auto_attribs=True)
class Draft:
    """
    The internals of a draft.  This represents the abstract state of the draft.
    This is where all the logic of a Booster Draft happens.
    """
    players: List[int]
    cards: List[str]
    _state: List[DraftPlayer] = attr.ib(factory=list)
    _opened_packs: int = 0
    number_of_packs: int = 3
    cards_per_booster: int = 15
    metadata: dict[str, Any] = attr.ib(factory=dict)
    stage: Stage = Stage.draft_registration
    spare_cards: int = 0  # number of cards left in the cube after allocating boosters
    name: str = ''

    def player_by_id(self, player_id: int) -> DraftPlayer:
        state = self._state[self.players.index(player_id)]
        if (state.id != player_id):
            raise KeyError(f"Player {player_id} not found, found {state.id} instead")
        return state

    def pack_of(self, player_id: int) -> Optional[Booster]:
        try:
            return self.player_by_id(player_id).current_pack
        except IndexError:
            return None

    def deck_of(self, player_id: int) -> List[str]:
        return self.player_by_id(player_id).deck

    def start(self, number_of_packs: int, cards_per_booster: int) -> List[DraftPlayer]:
        used_cards = number_of_packs * cards_per_booster * len(self.players)
        self.spare_cards = len(self.cards) - used_cards
        if self.spare_cards < 0:
            raise UserFeedbackException(f"Not enough cards {len(self.cards)} for {len(self.players)} with {number_of_packs} of {cards_per_booster}")
        self.number_of_packs = number_of_packs
        self.cards_per_booster = cards_per_booster
        random.shuffle(self.players)
        random.shuffle(self.cards)
        for i, player in enumerate(self.players):
            db = DraftPlayer(player, i)
            if player < 100:
                db.draftbot = True
            self._state.append(db)
        self.open_boosters_for_all_players()
        return self._state  # return all players to update

    def open_booster(self, player: DraftPlayer, number: int) -> Booster:
        card_list = [self.cards.pop() for _ in range(0, self.cards_per_booster)]
        booster = Booster(card_list, number)
        player.push_pack(booster, True)
        return booster

    def open_boosters_for_all_players(self) -> None:
        self._opened_packs += 1
        for player in self._state:
            self.open_booster(player, self._opened_packs)
        print("Opening pack for all players")

    def get_pending_players(self) -> List[DraftPlayer]:
        return [x for x in self._state if x.has_current_pack()]

    def is_draft_finished(self) -> bool:
        return (self.is_pack_finished() and (self._opened_packs >= self.number_of_packs)) or self.stage == Stage.draft_complete

    def is_pack_finished(self) -> bool:
        return len(self.get_pending_players()) == 0

    def pick(self, player_id: int, position: int) -> PickReturn:
        player = self.player_by_id(player_id)
        pack = player.pick(position)
        if pack is None:
            return PickReturn({}, [])

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
            next_player_id = self.get_next_player(player, pack)
            next_player = self.player_by_id(next_player_id)
            has_new_pack = next_player.push_pack(pack)
            if has_new_pack:
                users_to_update.append(next_player)

        if player.has_current_pack() and player not in users_to_update:
            users_to_update.append(player)

        result: Dict[DraftPlayer, List[str]] = {}
        new_booster = False
        for player in users_to_update:
            result[player] = []
            if player.has_one_card_in_current_pack():
                new_booster, effect = self.autopick(player)
                if effect:
                    player.face_up.append(player.last_pick())
                    pick_effects.append(effect)
                result[player].append(player.last_pick())

        if new_booster:
            for player in self._state:
                if player not in users_to_update:
                    result[player] = []

        return PickReturn(result, pick_effects)

    def check_if_draft_matters(self, player: DraftPlayer, pack: Booster) -> Optional[player_card_drafteffect]:
        pick = player.last_pick()
        if pick == 'Lore Seeker':  # Reveal Lore Seeker as you draft it. After you draft Lore Seeker, you may add a booster pack to the draft
            if self.spare_cards < self.cards_per_booster:
                # Don't add a booster if we don't have enough cards
                # revisit this when we have support for generating magic boosters
                return None
            self.spare_cards -= self.cards_per_booster
            self.open_booster(player, pack.number)
            return (player, pick, DraftEffect.add_booster_to_draft)
        if pick in ['Cogwork Librarian', "Leovold's Operative"]:  # Swap me into a later booster!
            return (player, pick, DraftEffect.no_immediate_effect)

        return None

    def autopick(self, player: DraftPlayer) -> Tuple[bool, Optional[player_card_drafteffect]]:
        if player.has_one_card_in_current_pack():
            pack = player.autopick()
            if not pack:
                return False, None
            pick_effect = self.check_if_draft_matters(player, pack)
            nextbooster = False
            if self.is_pack_finished() and not self.is_draft_finished():
                self.open_boosters_for_all_players()
                nextbooster = True
            return nextbooster, pick_effect
        return False, None

    def get_next_player(self, player: DraftPlayer, pack: Booster) -> int:
        i = player.seat
        if pack.number % 2 == 1:
            return self.players[(i + 1) % len(self.players)]
        return self.players[i - 1]

def was_last_pick_of_pack(pack: Booster) -> bool:
    return pack.is_empty()
