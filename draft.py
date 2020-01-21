from enum import Enum
import random
from booster import Booster

PickReturn = Enum('PickReturn', 'pick_error, in_progress, next_booster, finished')


class Draft:

	NUMBER_OF_BOOSTERS = 3
	BOOSTER_SIZE = 15
	FILE_NAME = 'EternalPennyDreadfulCube.txt'

	def __init__(self, players, file_name=FILE_NAME):
		self.file_name = file_name
		self.players = players
		random.shuffle(self.players)
		self.state = {}
		self.decks = { player:[] for player in players }

	def pack_of(self, player_id):
		return self.state[player_id]

	def deck_of(self, player_id):
		return self.decks[player_id]

	def start(self):
		self.cards = get_cards(self.file_name)
		random.shuffle(self.cards)
		self.booster_number = 0
		self.open_boosters()
		return self.state

	def open_boosters(self):
		for player in self.players:
			card_list = [self.cards.pop() for _ in range(0,self.BOOSTER_SIZE)]
			self.state[player] = Booster(card_list)
		self.booster_number += 1
		print("Opening pack {num}".format(num=self.booster_number))
		self.picked = []

	def pick(self, player, card_name=None, position=None):
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
			self.picked = []
			print(self.players)
			print(self.state[self.players[0]])
			if len(self.state[self.players[0]].cards) > 0:
				print("pass booster")
				self.pass_boosters()
				return PickReturn.next_booster
			elif self.booster_number < self.NUMBER_OF_BOOSTERS:
				print("open new booster")
				self.open_boosters()
				return PickReturn.next_booster
			else:
				print("Draft finished")
				return PickReturn.finished
		return PickReturn.in_progress

	def pass_boosters(self):
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


def get_cards(file_name):
	with open(file_name) as f:
		read_cards = f.read().splitlines()

	return read_cards


def main():
	players = ['a', 'b', 'c', 'd']
	draft = Draft(players)
	packs = draft.start()
	print(packs)
	state = PickReturn.in_progress
	while state != PickReturn.finished:
		for p in players:
			print("{player} deck: {cards}".format(player=p,cards=draft.decks[p]))
			print("{player}: {cards}".format(player=p,cards=packs[p].cards))

		for p in players:
			state = draft.pick(p, packs[p].cards[0])
			if state == PickReturn.next_booster:
				packs = draft.state

	print(draft.decks)
	#cube = draft.get_cards()
	#draft.show_decks(cube)
	#print(draft.deal_cards(cube))

if __name__ == "__main__":
	main()
