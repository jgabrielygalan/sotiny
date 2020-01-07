import random
import booster

class Draft:

	FILE_NAME = 'EternalPennyDreadfulCube.txt'

	def __init__(self, players, file_name=FILE_NAME):
		self.file_name = file_name
		self.players = random.shuffle(players)
		self.state = {}
		self.decks = {player:[] for player in players}
		
	def start(self):
		self.cards = get_cards(self.file_name)
		for player in players:
			card_list = []
			for i in range(15):
				card_list.append(cards.pop(random.randint(0, len(cards))))
			self.state[player] = Booster(card_list)
		self.booster_number = 1
		self.picked = []
		return self.state

	
	def pick(self, player, card_name):
		if player not in self.picked:
			self.state[player].pick(card_name)
			self.decks[player].append(card_name)
			self.picked.append(player)
		if len(picked) == len(self.players):
			self.picked = []
			if len(self.players[0]) > 0:
				self.pass_boosters()
			else:
				self.open_next_booster()
			return self.state
		return None

	def pass_boosters(self):
		last_booster = self.state[self.players[-1]]
		for player in self.players[0...]

	def show_decks(self, cards):
		print(cards)
		return


def get_cards(file_name):
	with open(file_name) as f:
		read_cards = f.read().splitlines()

	return read_cards


def main():
	draft = Draft(4)
	cube = draft.get_cards()
	draft.show_decks(cube)
	#print(draft.deal_cards(cube))

if __name__ == "__main__":
	main()
