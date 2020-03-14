from enum import Enum
import random
from booster import Booster
import utils

from typing import List, Optional
PickReturn = Enum('PickReturn', 'pick_error, in_progress, next_booster, finished, next_booster_autopick')


class Draft:
	def __init__(self, players: List[int], card_list: List[str]) -> None:
		self.cards = card_list
		self.players = players
		random.shuffle(self.players)
		self.state = {}
		self.decks = { player:[] for player in players }

	def pack_of(self, player_id: int) -> Booster:
		return self.state[player_id]

	def deck_of(self, player_id: int) -> List[str]:
		return self.decks[player_id]

	def get_pick_number(self) -> int:
		return self.pick_number

	def start(self, number_of_packs: int, cards_per_booster: int, cube: None = None) -> PickReturn:
		self.number_of_packs = number_of_packs
		self.cards_per_booster = cards_per_booster
		random.shuffle(self.cards)
		self.booster_number = 0
		self.open_boosters()
		if len(self.state[self.players[0]].cards) == 1: #autopick
			return PickReturn.next_booster_autopick
		return PickReturn.next_booster

	def open_boosters(self) -> None:
		self.pick_number = 1
		for player in self.players:
			card_list = [self.cards.pop() for _ in range(0,self.cards_per_booster)]
			self.state[player] = Booster(card_list)
		self.booster_number += 1
		print("Opening pack {num}".format(num=self.booster_number))
		self.picked = []

	def get_pending_players(self):
		return (set(self.players).difference(set(self.picked)))

	def pick(self, player: int, card_name: None = None, position: Optional[int] = None) -> PickReturn:
		if player not in self.picked:
			if card_name is not None:
				card = self.state[player].pick(card_name)
			elif position is not None:
				card = self.state[player].pick_by_position(position)
			else:
				print("Both card_name and position are None")
				return PickReturn.pick_error
			print("Player {p} picked {c}".format(p=player,c=card))
			if card is None:
				return PickReturn.pick_error
			self.decks[player].append(card)
			self.picked.append(player)
		if len(self.picked) == len(self.players):
			print("all players picked")
			print(self.players)
			print(self.state[self.players[0]])
			if len(self.state[self.players[0]].cards) > 0:
				print("pass booster")
				self.pass_boosters()
				if len(self.state[self.players[0]].cards) == 1: #autopick
					return PickReturn.next_booster_autopick
				return PickReturn.next_booster
			elif self.booster_number < self.number_of_packs:
				print("open new booster")
				self.open_boosters()
				if len(self.state[self.players[0]].cards) == 1: #autopick
					return PickReturn.next_booster_autopick
				return PickReturn.next_booster
			else:
				print("Draft finished")
				return PickReturn.finished
		return PickReturn.in_progress

	def autopick(self) -> PickReturn:
		if len(self.state[self.players[0]].cards) != 1:
			print(f"Error, can't autopick. Pack is: {self.state[self.players[0]].cards}")
		for player in self.players:
			state = self.pick(player, position=0)
		return state

	def pass_boosters(self) -> None:
		self.pick_number += 1
		if self.booster_number % 2 == 0:
			last = self.state[self.players[-1]]
			for i in range(len(self.players)-1, 0, -1):
		  		self.state[self.players[i]] = self.state[self.players[i-1]]
			self.state[self.players[0]] = last
		else:
			last = self.state[self.players[0]]
			for i in range(0, len(self.players)-1):
  				self.state[self.players[i]] = self.state[self.players[i+1]]
			self.state[self.players[-1]] = last
		self.picked = []
