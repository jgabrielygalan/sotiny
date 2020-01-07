import random

class Draft:

	CUBE_CARDS = 'EternalPennyDreadfulCube.txt'

	def __init__(self, num_players, cube_cards=CUBE_CARDS):
		self.cube_cards = cube_cards
		self.num_players = num_players
		decks = {f'player_{p}':[] for p in range(self.num_players)}
		print(f'{num_players} playing')
		
		
	def get_cards(self):
		with open(self.cube_cards) as f:
			read_cards = f.read().splitlines()

		return read_cards

	def deal_cards(self, cards_to_deal):
		players = 4
		draft = {}
		cards = cards_to_deal

		for p in range(players):
			draft[f'player_{p}'] = []

			for i in range(15):
				card = cards.pop(random.randint(0, len(cards)))
				draft[f'player_{p}'].append(card)
				
		return draft, cards

	def pick(self, card_name, player):

		return


	def show_decks(self):
		print(cards)
		return




def main():
	draft = Draft(4)
	cube = draft.get_cards()
	draft.show_decks()
	#print(draft.deal_cards(cube))

if __name__ == "__main__":
	main()