import random
from booster import Booster

class Draft:

	FILE_NAME = 'EternalPennyDreadfulCube.txt'

	def __init__(self, players, file_name=FILE_NAME):
		self.file_name = file_name
		self.players = players
		random.shuffle(self.players)
		self.state = {}
		self.decks = { player:[] for player in players }
		
	def start(self):
		self.cards = get_cards(self.file_name)
		self.booster_number = 0
		self.open_boosters()
		self.picked = []
		return self.state

	def open_boosters(self):
		for player in self.players:
			card_list = []
			for i in range(15):
				card_list.append(self.cards.pop(random.randint(0, len(self.cards))))
			self.state[player] = Booster(card_list)
		self.booster_number += 1
	
	def pick(self, player, card_name):
		if player not in self.picked:
			self.state[player].pick(card_name)
			self.decks[player].append(card_name)
			self.picked.append(player)
		if len(self.picked) == len(self.players):
			print("all players picked")
			self.picked = []
			if len(self.players[0]) > 0:
				print("pass booster")
				self.pass_boosters()
			else:
				print("open new booster")
				self.open_boosters()
			return self.state
		return None

	def pass_boosters(self):
		self.state = { list(self.players)[i + 1*(-1)^self.booster_number]: self.state[self.players[i]] for i in range(len(self.players)) }

	def show_deck(self, player):
		return decks[player]


def get_cards(file_name):
	with open(file_name) as f:
		read_cards = f.read().splitlines()

	return read_cards


def main():
	players = ['a', 'b', 'c', 'd']
	draft = Draft(players)
	packs = draft.start()
	for i in range(1,45):
		for p in players:
			print("{player} deck: {cards}".format(player=p,cards=draft.decks[p]))
			print("{player}: {cards}".format(player=p,cards=packs[p].cards))

		for p in players:
			new_packs = draft.pick(p, packs[p].cards[0])
		packs = new_packs

	#cube = draft.get_cards()
	#draft.show_decks(cube)
	#print(draft.deal_cards(cube))

if __name__ == "__main__":
	main()
